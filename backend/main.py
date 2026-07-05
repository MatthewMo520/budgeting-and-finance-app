"""App setup: middleware, error handling, startup migrations, router wiring.

Endpoints live in auth_routes.py and routers/ (transactions, plaid).
"""
import json
import os

import plaid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from database import engine, Base, SessionLocal
from models import User, LinkedAccount
import plaid_client as pc
from auth_routes import router as auth_router
from rate_limit import limiter

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
_allowed_origins = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,  # required so the refresh-token cookie is sent/accepted
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

# ── Plaid error handling ──────────────────────────────────────────────────────
@app.exception_handler(plaid.ApiException)
def plaid_exception_handler(request: Request, exc: plaid.ApiException):
    """Turn raw Plaid API exceptions into clean JSON instead of a 500 stack trace."""
    code, msg = "PLAID_ERROR", "There was a problem connecting to your bank. Please try again."
    try:
        err = json.loads(exc.body)
        code = err.get("error_code") or code
        if err.get("error_message"):
            msg = err["error_message"]
    except (ValueError, TypeError):
        pass
    # 400 for user-actionable errors; 502 for upstream/transient Plaid failures.
    user_actionable = {"ITEM_LOGIN_REQUIRED", "INVALID_CREDENTIALS", "INVALID_INPUT"}
    status_code = 400 if code in user_actionable else 502
    return JSONResponse(status_code=status_code, content={"detail": msg, "error_code": code})


Base.metadata.create_all(bind=engine)

# Lightweight idempotent migrations — create_all can't ADD columns to existing
# tables, so apply them here (Postgres "IF NOT EXISTS" makes this safe to re-run).
def _run_startup_migrations():
    from sqlalchemy import text
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category_overridden BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_expires TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_otp_enabled BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_otp_code VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_otp_expires TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_otp_attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE linked_accounts ADD COLUMN IF NOT EXISTS sync_cursor VARCHAR",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS merchant_name VARCHAR",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS logo_url VARCHAR",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS plaid_account_id VARCHAR",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS account_name VARCHAR",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS institution_name VARCHAR",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS anomaly_dismissed BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS digest_enabled BOOLEAN NOT NULL DEFAULT true",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS budget_alerts_enabled BOOLEAN NOT NULL DEFAULT true",
    ]
    try:
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
    except Exception as e:
        print(f"Startup migration warning: {e}")


_run_startup_migrations()


def _migrate_legacy_plaid_tokens():
    """Move any existing single `users.plaid_access_token` into linked_accounts
    so already-linked users keep working after the multi-account change."""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.plaid_access_token.isnot(None)).all()
        for u in users:
            if db.query(LinkedAccount).filter(LinkedAccount.user_id == u.id).first():
                continue
            try:
                env = pc.env_for_user(u)
                item_id = pc.get_item_id(u.plaid_access_token, env)
                db.add(LinkedAccount(user_id=u.id, access_token=u.plaid_access_token, item_id=item_id))
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Legacy Plaid token migration skipped for {u.email}: {e}")
    finally:
        db.close()


_migrate_legacy_plaid_tokens()

# Auto-provision the shared demo account when its credentials are configured
# (idempotent — safe to run on every startup). Requires the is_demo column.
if os.getenv("DEMO_EMAIL") and os.getenv("DEMO_PASSWORD"):
    try:
        from create_demo_user import main as _ensure_demo_account
        _ensure_demo_account()
    except Exception as e:
        print(f"Demo account setup skipped: {e}")

# ── Routers ───────────────────────────────────────────────────────────────────
from routers.transactions import router as transactions_router  # noqa: E402
from routers.plaid import router as plaid_router  # noqa: E402

app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(plaid_router)


@app.get("/")
def root():
    return {"status": "finance app running"}


# ── Month-end digest scheduler ────────────────────────────────────────────────
# Daily job that mails last month's recap during the first days of each month.
# digest_log makes it restart-safe (each user gets one digest per month).
if not os.getenv("TESTING"):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        def _run_digests():
            from datetime import datetime
            if datetime.utcnow().day > 3:
                return  # only send in the first days of a month
            from digest import send_month_digests
            db = SessionLocal()
            try:
                n = send_month_digests(db)
                if n:
                    print(f"Sent {n} month-end digest(s)")
            finally:
                db.close()

        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(_run_digests, "cron", hour=13, minute=0)
        _scheduler.start()
        _run_digests()  # catch up on startup too
    except Exception as e:
        print(f"Digest scheduler not started: {e}")
