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


def run_ml_for_user(user_id):
    """Background-task entry point: opens its own DB session and runs the
    pipeline. Used so ML doesn't block the HTTP response (the request-scoped
    session is already closed by the time a BackgroundTask runs)."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        run_ml_pipeline(db, user_id)
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

    # Categorize via a precedence chain: high-precision keyword rules first,
    # then Plaid's own category (accurate for real merchants), then the
    # char-n-gram ML model as a final fallback for anything still uncategorized.
    predicted = categorizer.predict([str(t.name) for t in txns])
    for t, model_pred in zip(txns, predicted):
        t.ml_category = rule_category(t.name) or t.category or model_pred

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
