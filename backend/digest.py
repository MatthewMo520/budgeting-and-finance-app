"""Month-end digest emails.

`build_digest` is a pure summary of one closed month; `send_month_digests`
mails it to every verified, non-demo user with transactions in that month,
exactly once per user per month (tracked in digest_log). A daily APScheduler
job in main.py calls it during the first days of each month.
"""
import calendar
from datetime import datetime

from sqlalchemy.orm import Session

from models import User, Transaction, Budget, DigestLog
from email_utils import send_monthly_digest
from ml import is_spend, compute_insights, LABEL_TO_DISPLAY


def _prev_month(month: str) -> str:
    y, m = map(int, month.split("-"))
    return f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"


def last_closed_month(now=None) -> str:
    now = now or datetime.utcnow()
    return _prev_month(now.strftime("%Y-%m"))


def build_digest(txns, month: str, budgets=None) -> dict:
    """Summarize one closed month: totals, MoM change, top categories,
    anomalies, and a few insights. Pure function."""
    def month_of(t):
        return t.date.strftime("%Y-%m")

    in_month = [t for t in txns if month_of(t) == month]
    prev = _prev_month(month)

    def spend_total(rows):
        return sum(t.amount for t in rows if is_spend(t.amount, getattr(t, "ml_category", None)))

    total_spend = spend_total(in_month)
    prev_spend = spend_total([t for t in txns if month_of(t) == prev])
    mom_pct = round((total_spend - prev_spend) / prev_spend * 100) if prev_spend > 0 else None

    by_display = {}
    for t in in_month:
        if not is_spend(t.amount, getattr(t, "ml_category", None)):
            continue
        display = LABEL_TO_DISPLAY.get((t.ml_category or "OTHER").upper(), "Other")
        by_display[display] = by_display.get(display, 0) + t.amount
    top_categories = sorted(by_display.items(), key=lambda kv: -kv[1])[:3]

    # Insights as of the last day of the digested month.
    y, m = map(int, month.split("-"))
    month_end = datetime(y, m, calendar.monthrange(y, m)[1], 23, 59)
    insights = compute_insights(txns, budgets, now=month_end)[:3]

    return {
        "month": month,
        "total_spend": round(total_spend, 2),
        "mom_pct": mom_pct,
        "top_categories": [{"category": c, "amount": round(a, 2)} for c, a in top_categories],
        "anomaly_count": sum(1 for t in in_month if getattr(t, "is_anomaly", False)),
        "transaction_count": len(in_month),
        "insights": insights,
    }


def send_month_digests(db: Session, month: str | None = None) -> int:
    """Send the digest for `month` (default: the last closed month) to every
    eligible user who hasn't received it. Returns the number sent."""
    month = month or last_closed_month()
    sent = 0
    users = db.query(User).filter(User.is_verified.is_(True), User.is_demo.is_(False)).all()
    for user in users:
        already = db.query(DigestLog).filter(
            DigestLog.user_id == user.id, DigestLog.month == month
        ).first()
        if already:
            continue
        txns = db.query(Transaction).filter(Transaction.user_id == user.id).all()
        if not any(t.date.strftime("%Y-%m") == month for t in txns):
            continue  # nothing to digest
        budgets = db.query(Budget).filter(Budget.user_id == user.id).all()
        digest = build_digest(txns, month, budgets)
        db.add(DigestLog(user_id=user.id, month=month))
        db.commit()
        try:
            send_monthly_digest(user.email, digest)
            sent += 1
        except Exception as e:
            print(f"Digest email to {user.email} failed (logged as sent, won't retry): {e}")
    return sent
