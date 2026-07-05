"""Transaction, budget, insight and ML endpoints (all user-scoped)."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User, Transaction, Budget, SavingsGoal
from ml import (
    run_ml_pipeline, detect_recurring, compute_insights, forecast_month,
    DISPLAY_TO_LABEL, is_spend,
)
from rate_limit import limiter

router = APIRouter(tags=["transactions"])


def _transactions_query(db: Session, user_id, month: Optional[str]):
    """User-scoped transaction query with an optional YYYY-MM month filter."""
    query = db.query(Transaction).filter(Transaction.user_id == user_id)
    if month:
        try:
            year, mon = map(int, month.split("-"))
            start_dt = datetime(year, mon, 1)
            end_dt = datetime(year + 1, 1, 1) if mon == 12 else datetime(year, mon + 1, 1)
            query = query.filter(Transaction.date >= start_dt, Transaction.date < end_dt)
        except (ValueError, AttributeError):
            pass
    return query.order_by(Transaction.date.desc())


def _serialize(t: Transaction) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "merchant_name": t.merchant_name,
        "logo_url": t.logo_url,
        "account_name": t.account_name,
        "institution_name": t.institution_name,
        "amount": t.amount,
        "date": t.date.isoformat(),
        "category": t.category,
        "ml_category": t.ml_category,
        "category_overridden": t.category_overridden,
        "is_anomaly": t.is_anomaly,
        "anomaly_score": t.anomaly_score,
        "anomaly_dismissed": t.anomaly_dismissed,
    }


@router.get("/transactions")
@limiter.limit("60/minute")
def get_transactions_endpoint(
    request: Request,
    month: Optional[str] = Query(None, description="Filter by month, format YYYY-MM"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    txns = _transactions_query(db, current_user.id, month).all()
    return [_serialize(t) for t in txns]


@router.get("/transactions/export")
@limiter.limit("10/minute")
def export_transactions(
    request: Request,
    month: Optional[str] = Query(None, description="Filter by month, format YYYY-MM"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the user's transactions as a CSV file."""
    import csv
    import io as _io

    def _safe(cell: str) -> str:
        # Neutralize spreadsheet formula injection (names are bank-supplied).
        return "'" + cell if cell[:1] in ("=", "+", "-", "@") else cell

    txns = _transactions_query(db, current_user.id, month).all()
    buf = _io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "name", "amount", "category", "anomaly"])
    for t in txns:
        writer.writerow([
            t.date.date().isoformat(),
            _safe(t.name or ""),
            f"{t.amount:.2f}",
            t.ml_category or t.category or "",
            "yes" if t.is_anomaly else "no",
        ])
    filename = f"transactions-{month}.csv" if month else "transactions-all.csv"
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class CategoryUpdate(BaseModel):
    category: str  # a display name from DISPLAY_TO_LABEL


@router.patch("/transactions/{txn_id}/category")
@limiter.limit("60/minute")
def update_transaction_category(
    request: Request,
    txn_id: str,
    body: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    label = DISPLAY_TO_LABEL.get(body.category)
    if not label:
        raise HTTPException(status_code=422, detail="Unknown category")
    txn = db.query(Transaction).filter(
        Transaction.id == txn_id, Transaction.user_id == current_user.id
    ).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    # Apply to all of the user's same-named transactions for consistency, and
    # mark them overridden so ML keeps the choice (and learns from it).
    db.query(Transaction).filter(
        Transaction.user_id == current_user.id, Transaction.name == txn.name
    ).update({Transaction.ml_category: label, Transaction.category_overridden: True})
    db.commit()
    return {"message": "Category updated", "ml_category": label}


class AnomalyUpdate(BaseModel):
    dismissed: bool


@router.patch("/transactions/{txn_id}/anomaly")
@limiter.limit("60/minute")
def update_transaction_anomaly(
    request: Request,
    txn_id: str,
    body: AnomalyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User feedback on an anomaly flag: dismissed=true means "this is expected"
    — the flag is cleared and ML re-runs won't re-flag the transaction."""
    import uuid as _uuid
    try:
        tid = _uuid.UUID(txn_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Transaction not found")
    txn = db.query(Transaction).filter(
        Transaction.id == tid, Transaction.user_id == current_user.id
    ).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    txn.anomaly_dismissed = body.dismissed
    if body.dismissed:
        txn.is_anomaly = False
    db.commit()
    return {"message": "Marked as expected" if body.dismissed else "Anomaly flag restored",
            "is_anomaly": txn.is_anomaly, "anomaly_dismissed": txn.anomaly_dismissed}


@router.get("/insights")
@limiter.limit("30/minute")
def get_insights(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Rule-generated observations: category spikes, new subscriptions,
    possible duplicate charges, budgets nearly used."""
    txns = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()
    return compute_insights(txns, budgets)


@router.get("/transactions/recurring")
@limiter.limit("30/minute")
def get_recurring(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    txns = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    return detect_recurring(txns)


@router.get("/transactions/summary")
@limiter.limit("60/minute")
def get_monthly_summary(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-month totals for the trend chart: spend, income, count.

    Category-aware: card payments and inter-account transfers are excluded from
    spend (they'd double-count purchases already logged) and transfers are
    excluded from income.
    """
    txns = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    agg = {}
    for t in txns:
        label = ((t.ml_category or t.category) or "").upper()
        a = agg.setdefault(t.date.strftime("%Y-%m"), {"spend": 0.0, "income": 0.0, "count": 0})
        a["count"] += 1
        if is_spend(t.amount, label):
            a["spend"] += t.amount
        elif t.amount < 0 and label not in ("TRANSFER_IN", "TRANSFER_OUT"):
            a["income"] += -t.amount
    return [
        {"month": m, "spend": round(v["spend"], 2), "income": round(v["income"], 2), "count": v["count"]}
        for m, v in sorted(agg.items())
    ]


@router.get("/transactions/months")
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


@router.post("/run-ml")
@limiter.limit("5/minute")
def run_ml(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = run_ml_pipeline(db, current_user.id)
    return result


@router.get("/forecast")
@limiter.limit("30/minute")
def get_forecast(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Projected end-of-month spend for the current month."""
    txns = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    return forecast_month(txns)


# ── Savings goals ─────────────────────────────────────────────────────────────

class GoalIn(BaseModel):
    name: str
    target_amount: float
    target_date: Optional[str] = None  # ISO date


def _net_saved_since(txns, since) -> float:
    """Net cash flow (income − spend, transfers excluded) since a datetime."""
    saved = 0.0
    for t in txns:
        if t.date < since:
            continue
        label = ((t.ml_category or t.category) or "").upper()
        if is_spend(t.amount, label):
            saved -= t.amount
        elif t.amount < 0 and label not in ("TRANSFER_IN", "TRANSFER_OUT"):
            saved += -t.amount
    return max(saved, 0.0)


@router.get("/goals")
@limiter.limit("60/minute")
def list_goals(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    goals = db.query(SavingsGoal).filter(SavingsGoal.user_id == current_user.id).order_by(SavingsGoal.created_at.asc()).all()
    txns = db.query(Transaction).filter(Transaction.user_id == current_user.id).all() if goals else []
    return [
        {
            "id": str(g.id),
            "name": g.name,
            "target_amount": g.target_amount,
            "target_date": g.target_date.isoformat() if g.target_date else None,
            "created_at": g.created_at.date().isoformat() if g.created_at else None,
            "saved": round(_net_saved_since(txns, g.created_at), 2) if g.created_at else 0.0,
        }
        for g in goals
    ]


@router.post("/goals", status_code=201)
@limiter.limit("30/minute")
def create_goal(request: Request, body: GoalIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    name = body.name.strip()
    if not 1 <= len(name) <= 60:
        raise HTTPException(status_code=422, detail="Goal name must be 1–60 characters")
    if body.target_amount <= 0:
        raise HTTPException(status_code=422, detail="Target must be positive")
    target_date = None
    if body.target_date:
        try:
            target_date = datetime.fromisoformat(body.target_date).date()
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid target date")
    goal = SavingsGoal(user_id=current_user.id, name=name,
                       target_amount=body.target_amount, target_date=target_date)
    db.add(goal)
    db.commit()
    return {"id": str(goal.id), "name": goal.name, "target_amount": goal.target_amount}


@router.delete("/goals/{goal_id}")
@limiter.limit("30/minute")
def delete_goal(request: Request, goal_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    import uuid as _uuid
    try:
        gid = _uuid.UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Goal not found")
    deleted = db.query(SavingsGoal).filter(
        SavingsGoal.id == gid, SavingsGoal.user_id == current_user.id
    ).delete()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"message": "Goal removed"}


# ── Budgets ───────────────────────────────────────────────────────────────────

class BudgetIn(BaseModel):
    category: str
    monthly_limit: float


@router.get("/budgets")
@limiter.limit("60/minute")
def list_budgets(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(Budget).filter(Budget.user_id == current_user.id).all()
    return [{"category": b.category, "monthly_limit": b.monthly_limit} for b in rows]


@router.put("/budgets")
@limiter.limit("30/minute")
def set_budget(request: Request, body: BudgetIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if body.category not in DISPLAY_TO_LABEL:
        raise HTTPException(status_code=422, detail="Unknown category")
    if body.monthly_limit <= 0:
        raise HTTPException(status_code=422, detail="Limit must be positive")
    b = db.query(Budget).filter(Budget.user_id == current_user.id, Budget.category == body.category).first()
    if b:
        b.monthly_limit = body.monthly_limit
    else:
        db.add(Budget(user_id=current_user.id, category=body.category, monthly_limit=body.monthly_limit))
    db.commit()
    return {"category": body.category, "monthly_limit": body.monthly_limit}


@router.delete("/budgets/{category}")
@limiter.limit("30/minute")
def delete_budget(request: Request, category: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db.query(Budget).filter(Budget.user_id == current_user.id, Budget.category == category).delete()
    db.commit()
    return {"message": "Budget removed"}
