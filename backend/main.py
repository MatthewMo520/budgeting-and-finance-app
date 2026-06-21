import json
import os
import time
from datetime import date, datetime, timedelta
from typing import Optional

import plaid
from fastapi import FastAPI, Depends, Query, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import engine, Base, get_db, SessionLocal
from models import User, Transaction, LinkedAccount
import plaid_client as pc
from ml import run_ml_pipeline, run_ml_for_user
from webhook_verify import verify_webhook
from auth import get_current_user
from auth_routes import router as auth_router

# ── Rate limiter ──────────────────────────────────────────────────────────────
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

app.include_router(auth_router)


@app.get("/")
def root():
    return {"status": "finance app running"}


# ── Plaid Link flow (real bank accounts) ─────────────────────────────────────

@app.post("/plaid/create-link-token")
@limiter.limit("20/minute")
def create_link_token(request: Request, current_user: User = Depends(get_current_user)):
    link_token = pc.create_link_token(str(current_user.id), pc.env_for_user(current_user))
    return {"link_token": link_token}


class ExchangeTokenRequest(BaseModel):
    public_token: str


@app.post("/plaid/exchange-token")
@limiter.limit("10/minute")
def exchange_token(
    request: Request,
    body: ExchangeTokenRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    environment = pc.env_for_user(current_user)
    access_token, item_id = pc.exchange_public_token(body.public_token, environment)
    _save_linked_account(db, current_user.id, access_token, item_id)
    db.commit()

    end = date.today()
    start = end - timedelta(days=365)
    transactions = _get_transactions_or_none(access_token, start, end, environment)
    if transactions is None:
        # Production: Plaid is still pulling history. The bank is linked; the
        # webhook (or a manual Sync) will load transactions once they're ready.
        return {"transactions_synced": 0, "pending": True,
                "message": "Bank linked! Your transactions are still being prepared — check back in a minute and hit Sync."}
    added = _upsert_transactions(db, current_user.id, transactions)
    background_tasks.add_task(run_ml_for_user, current_user.id)
    return {"transactions_synced": added}


# ── Transaction sync ──────────────────────────────────────────────────────────

@app.post("/plaid/sync")
@limiter.limit("10/minute")
def sync_transactions(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = db.query(LinkedAccount).filter(LinkedAccount.user_id == current_user.id).all()
    if not accounts:
        raise HTTPException(status_code=400, detail="No bank account linked.")

    environment = pc.env_for_user(current_user)
    end = date.today()
    start = end - timedelta(days=30)
    total_added = 0
    pending = False
    for acct in accounts:
        transactions = _get_transactions_or_none(acct.access_token, start, end, environment)
        if transactions is None:
            pending = True
            continue
        total_added += _upsert_transactions(db, current_user.id, transactions)

    if total_added > 0:
        background_tasks.add_task(run_ml_for_user, current_user.id)
    if total_added == 0 and pending:
        return {"transactions_synced": 0, "pending": True,
                "message": "Your transactions are still being prepared by your bank — try again in a minute."}
    return {"transactions_synced": total_added, "message": f"Synced {total_added} new transactions"}


# ── Plaid webhook (auto-sync when transactions are ready) ─────────────────────

@app.post("/plaid/webhook")
async def plaid_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    body_bytes = await request.body()
    payload = json.loads(body_bytes or b"{}")
    item_id = payload.get("item_id")

    acct = db.query(LinkedAccount).filter(LinkedAccount.item_id == item_id).first() if item_id else None
    if not acct:
        return {"status": "ignored"}  # unknown item — nothing to do

    user = db.query(User).filter(User.id == acct.user_id).first()
    environment = pc.env_for_user(user) if user else pc.PLAID_ENV
    if not verify_webhook(request.headers.get("plaid-verification"), body_bytes, environment):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Transaction updates → sync that item in the background, then run ML.
    if payload.get("webhook_type") == "TRANSACTIONS" and payload.get("webhook_code") in (
        "INITIAL_UPDATE", "HISTORICAL_UPDATE", "DEFAULT_UPDATE", "SYNC_UPDATES_AVAILABLE",
    ):
        background_tasks.add_task(_sync_account_async, str(acct.id))
    return {"status": "ok"}


# ── Sandbox setup (dev only) ──────────────────────────────────────────────────

@app.post("/setup-sandbox")
@limiter.limit("5/minute")
def setup_sandbox(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Dev-only: never allow fake data to overwrite a real linked account in prod.
    if os.getenv("PLAID_ENV") == "production":
        raise HTTPException(status_code=403, detail="Sandbox setup is disabled in production.")

    public_token = pc.create_sandbox_token()
    access_token, item_id = pc.exchange_public_token(public_token)
    _save_linked_account(db, current_user.id, access_token, item_id)
    db.commit()

    time.sleep(10)

    end = date.today()
    start = end - timedelta(days=365)
    transactions = pc.get_transactions(access_token, start, end)
    added = _upsert_transactions(db, current_user.id, transactions)
    return {"transactions_synced": added}


# ── ML ────────────────────────────────────────────────────────────────────────

@app.post("/run-ml")
@limiter.limit("5/minute")
def run_ml(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = run_ml_pipeline(db, current_user.id)
    return result


# ── Transactions ──────────────────────────────────────────────────────────────

@app.get("/transactions")
@limiter.limit("60/minute")
def get_transactions_endpoint(
    request: Request,
    month: Optional[str] = Query(None, description="Filter by month, format YYYY-MM"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)

    if month:
        try:
            year, mon = map(int, month.split("-"))
            start_dt = datetime(year, mon, 1)
            end_dt = datetime(year + 1, 1, 1) if mon == 12 else datetime(year, mon + 1, 1)
            query = query.filter(Transaction.date >= start_dt, Transaction.date < end_dt)
        except (ValueError, AttributeError):
            pass

    txns = query.order_by(Transaction.date.desc()).all()
    return [_serialize(t) for t in txns]


@app.get("/transactions/months")
@limiter.limit("60/minute")
def get_available_months(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(func.to_char(Transaction.date, "YYYY-MM").label("month"))
        .filter(Transaction.user_id == current_user.id)
        .distinct()
        .order_by(func.to_char(Transaction.date, "YYYY-MM").desc())
        .all()
    )
    return [r.month for r in rows]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_linked_account(db: Session, user_id, access_token, item_id, institution_name=None):
    """Insert or update a LinkedAccount, deduping by Plaid item_id."""
    acct = db.query(LinkedAccount).filter(LinkedAccount.item_id == item_id).first()
    if acct:
        acct.access_token = access_token
        acct.user_id = user_id
        if institution_name:
            acct.institution_name = institution_name
    else:
        db.add(LinkedAccount(user_id=user_id, access_token=access_token,
                             item_id=item_id, institution_name=institution_name))


def _sync_account_async(account_id: str):
    """Background sync for one linked account (used by the Plaid webhook)."""
    db = SessionLocal()
    try:
        acct = db.query(LinkedAccount).filter(LinkedAccount.id == account_id).first()
        if not acct:
            return
        user = db.query(User).filter(User.id == acct.user_id).first()
        environment = pc.env_for_user(user) if user else pc.PLAID_ENV
        end = date.today()
        start = end - timedelta(days=365)
        transactions = _get_transactions_or_none(acct.access_token, start, end, environment)
        if not transactions:
            return
        added = _upsert_transactions(db, acct.user_id, transactions)
        if added > 0:
            run_ml_pipeline(db, acct.user_id)
    finally:
        db.close()


def _get_transactions_or_none(access_token, start, end, environment):
    """Fetch transactions, returning None if Plaid hasn't finished preparing them
    yet (PRODUCT_NOT_READY) — common in production right after linking."""
    try:
        return pc.get_transactions(access_token, start, end, environment)
    except plaid.ApiException as e:
        try:
            code = json.loads(e.body).get("error_code")
        except (ValueError, TypeError):
            code = None
        if code == "PRODUCT_NOT_READY":
            return None
        raise


def _upsert_transactions(db: Session, user_id, plaid_txns: list) -> int:
    # Fetch existing ids once and dedupe in memory instead of one query per txn.
    existing = {
        row[0] for row in db.query(Transaction.plaid_transaction_id)
        .filter(Transaction.user_id == user_id).all()
    }
    added = 0
    for t in plaid_txns:
        if t.transaction_id in existing:
            continue
        existing.add(t.transaction_id)
        txn = Transaction(
            user_id=user_id,
            plaid_transaction_id=t.transaction_id,
            name=t.name,
            amount=t.amount,
            date=datetime.combine(t.date, datetime.min.time()),
            category=t.personal_finance_category.primary if t.personal_finance_category else None,
        )
        db.add(txn)
        added += 1
    db.commit()
    return added


def _serialize(t: Transaction) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "amount": t.amount,
        "date": t.date.isoformat(),
        "category": t.category,
        "ml_category": t.ml_category,
        "is_anomaly": t.is_anomaly,
        "anomaly_score": t.anomaly_score,
    }
