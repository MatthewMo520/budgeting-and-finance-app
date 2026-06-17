import numpy as np
from sqlalchemy.orm import Session
from models import Transaction
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from seed_data import SEED_TRANSACTIONS
from load_kaggle_data import load_kaggle_training_data

# The categorizer is trained on a static corpus (hand-labeled seed data + the
# Kaggle dataset) and cached in memory, so it is built once per process instead
# of being retrained on every bank link / sync. It contains no user data, which
# also avoids leaking one user's transactions into another's model.
_categorizer = None


def _build_categorizer():
    seed_names = [s[0] for s in SEED_TRANSACTIONS]
    seed_categories = [s[2] for s in SEED_TRANSACTIONS]

    try:
        kaggle_names, kaggle_categories = load_kaggle_training_data()
    except Exception as e:
        print(f"Kaggle data not loaded: {e}")
        kaggle_names, kaggle_categories = [], []

    names = [str(n) for n in seed_names + kaggle_names]
    categories = seed_categories + kaggle_categories

    print(f"Training categorizer on {len(names)} static samples")
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer()),
        ("clf", RandomForestClassifier(n_estimators=100, random_state=42)),
    ])
    pipeline.fit(names, categories)
    return pipeline


def get_categorizer():
    global _categorizer
    if _categorizer is None:
        _categorizer = _build_categorizer()
    return _categorizer


def run_ml_pipeline(db: Session, user_id):
    """Categorize transactions and flag anomalies for a single user only.

    The anomaly detector is fit on this user's amounts so flags are relative to
    their own spending, and predictions are written only for their rows.
    """
    categorizer = get_categorizer()

    txns = db.query(Transaction).filter(Transaction.user_id == user_id).all()
    if not txns:
        return {"categorized": 0, "anomalies": 0}

    # Categorize (one batched predict over the user's transaction names)
    predicted = categorizer.predict([str(t.name) for t in txns])
    for t, cat in zip(txns, predicted):
        t.ml_category = cat

    # Anomaly detection on this user's amounts only
    amounts = np.array([t.amount for t in txns]).reshape(-1, 1)
    iso = IsolationForest(contamination=0.15, random_state=42)
    iso.fit(amounts)
    scores = iso.decision_function(amounts)
    preds = iso.predict(amounts)
    for t, score, pred in zip(txns, scores, preds):
        t.anomaly_score = float(score)
        t.is_anomaly = bool(pred == -1)

    db.commit()
    return {
        "categorized": len(txns),
        "anomalies": int(sum(1 for t in txns if t.is_anomaly)),
    }
