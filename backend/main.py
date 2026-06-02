from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import engine, Base, get_db
from models import User, Transaction
from plaid_client import create_sandbox_token, exchange_public_token, get_transactions
from datetime import datetime
from ml import run_ml_pipeline

app = FastAPI()
Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"status": "finance app running"}

@app.post("/setup-sandbox")
def setup_sandbox(db: Session = Depends(get_db)):
    import time
    
    public_token = create_sandbox_token()
    access_token = exchange_public_token(public_token)

    user = User(plaid_access_token=access_token)
    db.add(user)
    db.commit()
    db.refresh(user)

    time.sleep(10)  # wait for Plaid sandbox to initialize transactions

    transactions = get_transactions(access_token)
    for t in transactions:
        txn = Transaction(
            user_id=user.id,
            plaid_transaction_id=t.transaction_id,
            name=t.name,
            amount=t.amount,
            date=datetime.combine(t.date, datetime.min.time()),
            category=t.personal_finance_category.primary if t.personal_finance_category else None
        )
        db.add(txn)
    db.commit()

    return {"user_id": str(user.id), "transactions_stored": len(transactions)}

@app.post("/run-ml")
def run_ml(db: Session = Depends(get_db)):
    result = run_ml_pipeline(db)
    return result

@app.get("/transactions")
def get_transactions_endpoint(db: Session = Depends(get_db)):
    txns = db.query(Transaction).all()
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "amount": t.amount,
            "date": t.date.isoformat(),
            "category": t.category,
            "ml_category": t.ml_category,
            "is_anomaly": t.is_anomaly,
            "anomaly_score": t.anomaly_score
        }
        for t in txns
    ]