import numpy as np
from sqlalchemy.orm import Session
from models import Transaction
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from seed_data import SEED_TRANSACTIONS
import pickle

def train_categorizer(db: Session):
    txns = db.query(Transaction).filter(Transaction.category != None).all()

    names = [t.name for t in txns] + [s[0] for s in SEED_TRANSACTIONS]
    categories = [t.category for t in txns] + [s[2] for s in SEED_TRANSACTIONS]

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer()),
        ("clf", RandomForestClassifier(n_estimators=100, random_state=42))
    ])
    pipeline.fit(names, categories)

    with open("categorizer.pkl", "wb") as f:
        pickle.dump(pipeline, f)

    return pipeline

def predict_category(name: str, pipeline) -> str:
    return pipeline.predict([name])[0]

def train_anomaly_detector(db: Session):
    txns = db.query(Transaction).all()
    amounts = np.array([t.amount for t in txns]).reshape(-1, 1)

    iso = IsolationForest(contamination=0.15, random_state=42)
    iso.fit(amounts)

    with open("anomaly.pkl", "wb") as f:
        pickle.dump(iso, f)

    return iso

def run_ml_pipeline(db: Session):
    categorizer = train_categorizer(db)
    anomaly_detector = train_anomaly_detector(db)

    txns = db.query(Transaction).all()
    for t in txns:
        t.ml_category = predict_category(t.name, categorizer)
        score = anomaly_detector.decision_function([[t.amount]])[0]
        t.is_anomaly = bool(anomaly_detector.predict([[t.amount]])[0] == -1)
        t.anomaly_score = float(score)

    db.commit()
    return {"categorized": len(txns), "anomalies": sum(1 for t in txns if t.is_anomaly)}