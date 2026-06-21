from sqlalchemy import Column, String, Float, DateTime, Boolean, ForeignKey, Integer, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database import Base
from crypto import EncryptedString
import uuid
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    plaid_access_token = Column(EncryptedString, nullable=True)
    totp_secret = Column(EncryptedString, nullable=True)
    totp_enabled = Column(Boolean, default=False)
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    username = Column(String, nullable=True)
    profile_picture = Column(String, nullable=True)
    # Bumped to invalidate all of a user's existing JWTs (password change/reset).
    token_version = Column(Integer, nullable=False, default=0, server_default=text("0"))
    # Shared demo account: exempt from mandatory 2FA, routed to Plaid sandbox.
    is_demo = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime, default=datetime.utcnow)


class LinkedAccount(Base):
    """One linked Plaid Item (bank connection). A user can have several."""
    __tablename__ = "linked_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    access_token = Column(EncryptedString, nullable=False)
    item_id = Column(String, unique=True, nullable=False, index=True)  # maps Plaid webhooks → account
    institution_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Budget(Base):
    """A monthly spending limit for one display category, per user."""
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_budget_user_category"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, nullable=False)  # display name e.g. "Dining"
    monthly_limit = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plaid_transaction_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(DateTime, nullable=False)
    category = Column(String, nullable=True)
    ml_category = Column(String, nullable=True)
    # True when the user manually set the category — ML won't overwrite it, and
    # it's used as per-user training feedback for same-named transactions.
    category_overridden = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    is_anomaly = Column(Boolean, default=False)
    anomaly_score = Column(Float, nullable=True)
