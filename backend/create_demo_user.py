"""Create (or update) the shared demo account.

The demo account is verified, exempt from 2FA, and routed to Plaid sandbox, so
testers can try the app — including the "Connect bank" flow with sandbox creds
(user_good / pass_good) — without creating an account or touching real banks.

Usage (inside the backend container):
    python create_demo_user.py

Credentials default to demo@fintrack.app / FintrackDemo123, overridable via the
DEMO_EMAIL / DEMO_PASSWORD environment variables.
"""
import os

from auth import hash_password
from database import SessionLocal
from models import User

DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@fintrack.app")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "FintrackDemo123")


def main():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if user is None:
            user = User(email=DEMO_EMAIL)
            db.add(user)
        user.hashed_password = hash_password(DEMO_PASSWORD)
        user.is_verified = True
        user.is_demo = True
        user.totp_enabled = False
        user.totp_secret = None
        user.username = user.username or "Demo User"
        db.commit()
        print(f"Demo account ready:\n  email:    {DEMO_EMAIL}\n  password: {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
