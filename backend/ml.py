import numpy as np
from sqlalchemy.orm import Session
from models import Transaction
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from seed_data import SEED_TRANSACTIONS

# Categorization is a hybrid: deterministic keyword rules first (bank statements
# have very predictable patterns and real names rarely match a tiny ML corpus),
# then a char-n-gram ML model as a fallback for anything the rules don't cover.
# Labels are Plaid personal_finance_category primaries (see frontend categories.jsx).
#
# NOTE: the old Kaggle source is intentionally dropped — its "Merchant Name"
# column is a numeric hashed ID, so it taught the model nothing about real names
# and pushed every unseen merchant to the majority class ("Shopping").

# Ordered (first match wins); each entry is (substrings, label). Matched
# case-insensitively against the transaction name.
_RULES = [
    # Bank-statement patterns (not merchants) — most specific first
    (("payroll", "gusto", "direct dep", "adp pay", "salary", "paycheck"), "INCOME"),
    (("interest paid", "dividend", "interest earned"), "INCOME"),
    (("credit card", "card payment", "cc payment", "visa payment", "mastercard payment", "amex payment"), "LOAN_PAYMENTS"),
    (("loan", "osap", "student loan", "mortgage"), "LOAN_PAYMENTS"),
    (("cd deposit", "transfer to", "ach transfer", "online transfer", "wire transfer", "withdrawal", "atm "), "TRANSFER_OUT"),
    (("deposit", "transfer from", "zelle", "venmo", "e-transfer"), "TRANSFER_IN"),
    # Transportation (incl. fuel)
    (("uber", "lyft", "transit", "ttc", "metro ", "go transit", "parking", "shell", "chevron", "exxon", "petro", "gas station"), "TRANSPORTATION"),
    # Travel
    (("airline", "airlines", "air canada", "delta air", "united air", "hotel", "marriott", "hilton", "airbnb", "expedia", "booking.com", "flight", "hostel"), "TRAVEL"),
    # Food & drink
    (("mcdonald", "starbucks", "subway", "pizza", "chipotle", "restaurant", "coffee", "cafe", "kfc", "wendy", "taco", "burger", "doordash", "uber eats", "grubhub", "dunkin", "tim horton", "diner", "grill"), "FOOD_AND_DRINK"),
    # Groceries
    (("whole foods", "safeway", "kroger", "trader joe", "costco", "grocery", "supermarket", "aldi", "loblaw", "no frills", "sobeys"), "GROCERIES"),
    # Entertainment / recreation
    (("netflix", "spotify", "steam", "amc", "cinema", "theatre", "theater", "climbing", "gym", "fitness", "hulu", "disney", "playstation", "xbox", "concert", "recreation"), "ENTERTAINMENT"),
    # Utilities / telecom / rent
    (("hydro", "rogers", "enbridge", "comcast", "at&t", "verizon", "utility", "electric bill", "rent payment", "water bill", "internet", "wireless"), "RENT_AND_UTILITIES"),
    # Medical
    (("pharmacy", "cvs", "walgreens", "clinic", "hospital", "dental", "doctor", "medical"), "MEDICAL"),
    # General merchandise / shopping
    (("amazon", "walmart", "target", "best buy", "ikea", "ebay", "etsy", "aliexpress"), "GENERAL_MERCHANDISE"),
]


def rule_category(name: str):
    """Return a category from keyword rules, or None if nothing matches."""
    n = (name or "").lower()
    for substrings, label in _RULES:
        if any(s in n for s in substrings):
            return label
    return None


# ── Spend accounting ──────────────────────────────────────────────────────────
# Transfer-like outflows are NOT spending: a credit-card payment moves money to
# the card whose purchases are already logged, so counting it would double-count
# every dollar. Same for transfers between the user's own accounts.
NON_SPEND_LABELS = frozenset({"TRANSFER_OUT", "TRANSFER_IN", "LOAN_PAYMENTS", "INCOME"})

# Display name → canonical Plaid-style label (shared by category edits, budgets
# and insights; the frontend mirror lives in categories.jsx).
DISPLAY_TO_LABEL = {
    "Dining": "FOOD_AND_DRINK", "Groceries": "GROCERIES", "Transport": "TRANSPORTATION",
    "Shopping": "GENERAL_MERCHANDISE", "Utilities": "RENT_AND_UTILITIES",
    "Entertainment": "ENTERTAINMENT", "Health": "MEDICAL", "Travel": "TRAVEL",
    "Income": "INCOME", "Transfer": "TRANSFER_OUT", "Payments": "LOAN_PAYMENTS",
    "Other": "OTHER",
}
LABEL_TO_DISPLAY = {v: k for k, v in DISPLAY_TO_LABEL.items()}


def is_spend(amount, label) -> bool:
    """True when a transaction counts toward spending totals."""
    return (amount or 0) > 0 and (label or "").upper() not in NON_SPEND_LABELS


# Char-n-gram ML fallback, trained once on the seed corpus and cached in memory.
_categorizer = None


def _build_categorizer():
    names = [str(s[0]) for s in SEED_TRANSACTIONS]
    categories = [s[2] for s in SEED_TRANSACTIONS]
    print(f"Training categorizer (char n-grams) on {len(names)} seed samples")
    pipeline = Pipeline([
        # char_wb n-grams generalize to unseen/dirty names (e.g. "McDonald's"
        # matches seed "McDonalds"; "Uber 063015 SF**POOL**" matches "Uber").
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=True)),
        ("clf", RandomForestClassifier(n_estimators=200, random_state=42)),
    ])
    pipeline.fit(names, categories)
    return pipeline


def get_categorizer():
    global _categorizer
    if _categorizer is None:
        _categorizer = _build_categorizer()
    return _categorizer


def _normalize_merchant(name: str) -> str:
    """Loose key for grouping the same merchant across months."""
    import re
    s = re.sub(r"[^a-z ]", " ", (name or "").lower())
    return " ".join(s.split()[:3])


def detect_recurring(txns):
    """Heuristic recurring-charge detection: group spend by merchant, then flag
    groups with a regular cadence (weekly/biweekly/monthly) and stable amount."""
    import statistics
    from collections import defaultdict

    groups = defaultdict(list)
    for t in txns:
        # Spend outflows only — card payments/transfers aren't subscriptions.
        if not is_spend(t.amount, getattr(t, "ml_category", None)):
            continue
        groups[_normalize_merchant(t.name)].append(t)

    results = []
    for items in groups.values():
        if len(items) < 3:
            continue
        items.sort(key=lambda x: x.date)
        gaps = [(items[i + 1].date - items[i].date).days for i in range(len(items) - 1)]
        gaps = [g for g in gaps if g > 0]
        if len(gaps) < 2:
            continue
        avg_gap = statistics.mean(gaps)
        gap_std = statistics.pstdev(gaps)
        amounts = [i.amount for i in items]
        amt_mean = statistics.mean(amounts)
        amt_cv = (statistics.pstdev(amounts) / amt_mean) if amt_mean else 1

        # Regular cadence (~weekly to ~monthly) and stable amount.
        if 5 <= avg_gap <= 40 and gap_std <= 8 and amt_cv <= 0.20:
            freq = "weekly" if avg_gap < 11 else ("biweekly" if avg_gap < 20 else "monthly")
            results.append({
                "name": items[-1].name,
                "amount": round(amt_mean, 2),
                "frequency": freq,
                "occurrences": len(items),
                "first_date": items[0].date.date().isoformat(),
                "last_date": items[-1].date.date().isoformat(),
                "category": items[-1].ml_category,
                "estimated_monthly": round(amt_mean * (30.0 / avg_gap), 2),
            })
    results.sort(key=lambda r: -r["estimated_monthly"])
    return results


# ── Insights ──────────────────────────────────────────────────────────────────

def _month_key(dt):
    return dt.strftime("%Y-%m")


def _prev_month_keys(now, n=3):
    y, m = now.year, now.month
    keys = []
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        keys.append(f"{y:04d}-{m:02d}")
    return keys


def compute_insights(txns, budgets=None, now=None):
    """Rule-generated observations about the user's spending. Pure function —
    takes ORM rows (or anything with name/amount/date/ml_category) and returns
    [{type, severity, title, detail}], most important first."""
    from datetime import datetime, timedelta
    from collections import defaultdict
    import statistics

    now = now or datetime.utcnow()
    this_month = _month_key(now)
    prev_keys = _prev_month_keys(now, 3)
    insights = []

    spend_txns = [t for t in txns if is_spend(t.amount, getattr(t, "ml_category", None))]

    # 1) Category spikes: this month ≥ 140% of the trailing-3-month average.
    by_cat_month = defaultdict(lambda: defaultdict(float))
    for t in spend_txns:
        by_cat_month[(t.ml_category or "OTHER").upper()][_month_key(t.date)] += t.amount
    for label, months in by_cat_month.items():
        cur = months.get(this_month, 0)
        avg = statistics.mean(months.get(k, 0) for k in prev_keys)
        if avg > 0 and cur >= 1.4 * avg and cur - avg >= 50:
            display = LABEL_TO_DISPLAY.get(label, label.title())
            insights.append({
                "type": "spike", "severity": "warn",
                "title": f"{display} spending is up {round((cur / avg - 1) * 100)}%",
                "detail": f"${cur:,.0f} so far this month vs your ${avg:,.0f} three-month average.",
            })

    # 2) New subscriptions: recurring charges that started in the last 45 days.
    for r in detect_recurring(txns):
        first = datetime.fromisoformat(r["first_date"])
        if (now - first).days <= 45:
            insights.append({
                "type": "subscription", "severity": "info",
                "title": f"New recurring charge: {r['name']}",
                "detail": f"${r['amount']:,.2f} {r['frequency']} (≈ ${r['estimated_monthly']:,.0f}/mo), first seen {r['first_date']}.",
            })

    # 3) Possible duplicates: same merchant + same amount within 2 days (last 30 days).
    recent = [t for t in spend_txns if (now - t.date).days <= 30]
    seen = defaultdict(list)
    for t in recent:
        seen[(_normalize_merchant(t.name), round(t.amount, 2))].append(t)
    for (merchant, amount), items in seen.items():
        if len(items) < 2 or not merchant:
            continue
        items.sort(key=lambda x: x.date)
        if any((items[i + 1].date - items[i].date).days <= 2 for i in range(len(items) - 1)):
            insights.append({
                "type": "duplicate", "severity": "warn",
                "title": f"Possible duplicate charge: {items[-1].name}",
                "detail": f"${amount:,.2f} charged {len(items)} times within a couple of days — worth a look.",
            })

    # 4) Budgets nearly used (current month).
    if budgets:
        display_spend = defaultdict(float)
        for t in spend_txns:
            if _month_key(t.date) == this_month:
                display_spend[LABEL_TO_DISPLAY.get((t.ml_category or "OTHER").upper(), "Other")] += t.amount
        for b in budgets:
            spent = display_spend.get(b.category, 0)
            if b.monthly_limit > 0 and spent >= 0.9 * b.monthly_limit:
                pct = round(spent / b.monthly_limit * 100)
                insights.append({
                    "type": "budget", "severity": "alert" if pct >= 100 else "warn",
                    "title": f"{b.category} budget {'exceeded' if pct >= 100 else 'almost used'}",
                    "detail": f"${spent:,.0f} of your ${b.monthly_limit:,.0f} limit ({pct}%).",
                })

    order = {"alert": 0, "warn": 1, "info": 2}
    insights.sort(key=lambda i: order.get(i["severity"], 3))
    return insights


# ── Cash-flow forecast ────────────────────────────────────────────────────────

def forecast_month(txns, now=None):
    """Project end-of-month spend: what's spent so far, plus day-to-day spend at
    the trailing-90-day daily rate, plus known monthly recurring charges whose
    usual day hasn't arrived yet. Monthly recurring merchants are excluded from
    the daily rate so they aren't counted twice. Pure function."""
    import calendar
    from datetime import datetime, timedelta

    now = now or datetime.utcnow()
    this_month = _month_key(now)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    days_left = days_in_month - now.day

    spend_txns = [t for t in txns if is_spend(t.amount, getattr(t, "ml_category", None))]
    spent = sum(t.amount for t in spend_txns if _month_key(t.date) == this_month)

    recurring = [r for r in detect_recurring(txns) if r["frequency"] == "monthly"]
    recurring_names = {_normalize_merchant(r["name"]) for r in recurring}

    cutoff = now - timedelta(days=90)
    recent_daily = [
        t for t in spend_txns
        if t.date >= cutoff and _normalize_merchant(t.name) not in recurring_names
    ]
    daily_rate = sum(t.amount for t in recent_daily) / 90 if recent_daily else 0.0

    upcoming = []
    for r in recurring:
        last = datetime.fromisoformat(r["last_date"])
        if _month_key(last) == this_month:
            continue  # already charged this month
        expected_day = min(last.day, days_in_month)
        if expected_day > now.day:
            upcoming.append({"name": r["name"], "amount": r["amount"], "expected_day": expected_day})

    projected = spent + daily_rate * days_left + sum(u["amount"] for u in upcoming)
    return {
        "month": this_month,
        "spent_so_far": round(spent, 2),
        "daily_rate": round(daily_rate, 2),
        "days_left": days_left,
        "upcoming_recurring": upcoming,
        "projected_spend": round(projected, 2),
    }


def run_ml_for_user(user_id):
    """Background-task entry point: opens its own DB session and runs the
    pipeline. Used so ML doesn't block the HTTP response (the request-scoped
    session is already closed by the time a BackgroundTask runs)."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        run_ml_pipeline(db, user_id)
        # New transactions may have pushed a budget past its threshold.
        try:
            from budget_alerts import check_and_send_budget_alerts
            check_and_send_budget_alerts(db, user_id)
        except Exception as e:
            print(f"Budget alert check failed (continuing): {e}")
    finally:
        db.close()


def run_ml_pipeline(db: Session, user_id):
    """Categorize transactions and flag anomalies for a single user only.

    The anomaly detector is fit on this user's amounts so flags are relative to
    their own spending, and predictions are written only for their rows.
    """
    categorizer = get_categorizer()

    txns = db.query(Transaction).filter(Transaction.user_id == user_id).all()
    if not txns:
        return {"categorized": 0, "anomalies": 0}

    # Per-user feedback: learn from this user's manual corrections so future
    # transactions with the same merchant name get the corrected category.
    corrections = {
        (t.name or "").strip().lower(): t.ml_category
        for t in txns
        if getattr(t, "category_overridden", False) and t.ml_category
    }

    # Categorize via a precedence chain: manual corrections → keyword rules →
    # Plaid's own category → char-n-gram ML model. User-overridden rows are
    # left untouched.
    predicted = categorizer.predict([str(t.name) for t in txns])
    for t, model_pred in zip(txns, predicted):
        if getattr(t, "category_overridden", False):
            continue
        learned = corrections.get((t.name or "").strip().lower())
        t.ml_category = learned or rule_category(t.name) or t.category or model_pred

    # Anomaly detection — fit per user on multiple features so a charge is
    # judged relative to that user's own patterns, not just raw size:
    #   1. absolute amount
    #   2. amount relative to the average for its category (so a big-but-normal
    #      category like Rent isn't always flagged, but an unusually large
    #      Dining charge is)
    #   3. day of month (catches off-cycle timing)
    abs_amounts = np.array([abs(t.amount) for t in txns], dtype=float)
    cats = [t.ml_category or "UNKNOWN" for t in txns]
    cat_means = {}
    for c in set(cats):
        vals = abs_amounts[[i for i, cc in enumerate(cats) if cc == c]]
        cat_means[c] = vals.mean() if len(vals) and vals.mean() > 0 else 1.0
    rel_amounts = np.array([abs_amounts[i] / cat_means[cats[i]] for i in range(len(txns))])
    days = np.array([t.date.day for t in txns], dtype=float)

    features = np.column_stack([abs_amounts, rel_amounts, days])
    iso = IsolationForest(contamination=0.15, random_state=42)
    iso.fit(features)
    scores = iso.decision_function(features)
    preds = iso.predict(features)
    for t, score, pred in zip(txns, scores, preds):
        t.anomaly_score = float(score)
        t.is_anomaly = bool(pred == -1)

    db.commit()
    return {
        "categorized": len(txns),
        "anomalies": int(sum(1 for t in txns if t.is_anomaly)),
    }
