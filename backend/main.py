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

from database import engine, Base, get_db
from models import User, Transaction
import plaid_client as pc
from ml import run_ml_pipeline, run_ml_for_user
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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
    access_token = pc.exchange_public_token(body.public_token, environment)
    current_user.plaid_access_token = access_token
    db.commit()

    end = date.today()
    start = end - timedelta(days=365)
    transactions = pc.get_transactions(access_token, start, end, environment)
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
    if not current_user.plaid_access_token:
        raise HTTPException(status_code=400, detail="No bank account linked.")

    end = date.today()
    start = end - timedelta(days=30)
    transactions = pc.get_transactions(current_user.plaid_access_token, start, end, pc.env_for_user(current_user))
    added = _upsert_transactions(db, current_user.id, transactions)
    if added > 0:
        background_tasks.add_task(run_ml_for_user, current_user.id)
    return {"transactions_synced": added, "message": f"Synced {added} new transactions"}


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
    access_token = pc.exchange_public_token(public_token)
    current_user.plaid_access_token = access_token
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
