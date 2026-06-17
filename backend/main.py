import os
import time
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import User, Transaction
import plaid_client as pc
from ml import run_ml_pipeline
from auth import get_current_user
from auth_routes import router as auth_router

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

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
    return response

Base.metadata.create_all(bind=engine)
app.include_router(auth_router)


@app.get("/")
def root():
    return {"status": "finance app running"}


# ── Plaid Link flow (real bank accounts) ─────────────────────────────────────

@app.post("/plaid/create-link-token")
@limiter.limit("20/minute")
def create_link_token(request: Request, current_user: User = Depends(get_current_user)):
    link_token = pc.create_link_token(str(current_user.id))
    return {"link_token": link_token}


class ExchangeTokenRequest(BaseModel):
    public_token: str


@app.post("/plaid/exchange-token")
@limiter.limit("10/minute")
def exchange_token(
    request: Request,
    body: ExchangeTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    access_token = pc.exchange_public_token(body.public_token)
    current_user.plaid_access_token = access_token
    db.commit()

    end = date.today()
    start = end - timedelta(days=365)
    transactions = pc.get_transactions(access_token, start, end)
    added = _upsert_transactions(db, current_user.id, transactions)
    run_ml_pipeline(db)
    return {"transactions_synced": added}


# ── Transaction sync ──────────────────────────────────────────────────────────

@app.post("/plaid/sync")
@limiter.limit("10/minute")
def sync_transactions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.plaid_access_token:
        raise HTTPException(status_code=400, detail="No bank account linked.")

    end = date.today()
    start = end - timedelta(days=30)
    transactions = pc.get_transactions(current_user.plaid_access_token, start, end)
    added = _upsert_transactions(db, current_user.id, transactions)
    if added > 0:
        run_ml_pipeline(db)
    return {"transactions_synced": added, "message": f"Synced {added} new transactions"}


# ── Sandbox setup (dev only) ──────────────────────────────────────────────────

@app.post("/setup-sandbox")
@limiter.limit("5/minute")
def setup_sandbox(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    result = run_ml_pipeline(db)
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
    added = 0
    for t in plaid_txns:
        if db.query(Transaction).filter(
            Transaction.plaid_transaction_id == t.transaction_id
        ).first():
            continue
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
