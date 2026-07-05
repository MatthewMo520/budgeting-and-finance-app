"""Budget threshold alert emails.

After a sync adds transactions (called at the end of the ML background task),
check each budget against the current month's spend and email the user when it
crosses 90% or 100%. The budget_alerts table records what was already sent so
each (user, category, month, threshold) alert goes out exactly once.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from models import User, Transaction, Budget, BudgetAlert
from email_utils import send_budget_alert_email
from ml import is_spend, LABEL_TO_DISPLAY


def check_and_send_budget_alerts(db: Session, user_id) -> None:
    budgets = db.query(Budget).filter(Budget.user_id == user_id).all()
    if not budgets:
        return
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.budget_alerts_enabled:
        return

    now = datetime.utcnow()
    month = now.strftime("%Y-%m")
    txns = db.query(Transaction).filter(Transaction.user_id == user_id).all()
    spent_by_display = {}
    for t in txns:
        if t.date.strftime("%Y-%m") != month or not is_spend(t.amount, t.ml_category):
            continue
        display = LABEL_TO_DISPLAY.get((t.ml_category or "OTHER").upper(), "Other")
        spent_by_display[display] = spent_by_display.get(display, 0) + t.amount

    for b in budgets:
        spent = spent_by_display.get(b.category, 0)
        if b.monthly_limit <= 0:
            continue
        for threshold in (100, 90):  # highest crossed threshold wins
            if spent < b.monthly_limit * threshold / 100:
                continue
            already = db.query(BudgetAlert).filter(
                BudgetAlert.user_id == user_id, BudgetAlert.category == b.category,
                BudgetAlert.month == month, BudgetAlert.threshold == threshold,
            ).first()
            if not already:
                db.add(BudgetAlert(user_id=user_id, category=b.category, month=month, threshold=threshold))
                db.commit()
                try:
                    send_budget_alert_email(user.email, b.category, spent, b.monthly_limit, threshold)
                except Exception:
                    pass  # alert row stays so we don't retry-spam on flaky email
            break
