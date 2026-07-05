from sqlalchemy import Column, String, Float, Date, DateTime, Boolean, ForeignKey, Integer, text, UniqueConstraint
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
    verification_token_expires = Column(DateTime, nullable=True)
    plaid_access_token = Column(EncryptedString, nullable=True)
    totp_secret = Column(EncryptedString, nullable=True)
    totp_enabled = Column(Boolean, default=False)
    # Email-code 2FA (alternative to TOTP; either — or both — can be enabled).
    email_otp_enabled = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    email_otp_code = Column(String, nullable=True)  # sha256 hash of the 6-digit code
    email_otp_expires = Column(DateTime, nullable=True)
    email_otp_attempts = Column(Integer, nullable=False, default=0, server_default=text("0"))
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    username = Column(String, nullable=True)
    profile_picture = Column(String, nullable=True)
    # Bumped to invalidate all of a user's existing JWTs (password change/reset).
    token_version = Column(Integer, nullable=False, default=0, server_default=text("0"))
    # Shared demo account: exempt from mandatory 2FA, routed to Plaid sandbox.
    is_demo = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    # Email notification preferences
    digest_enabled = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    budget_alerts_enabled = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime, default=datetime.utcnow)


class LinkedAccount(Base):
    """One linked Plaid Item (bank connection). A user can have several."""
    __tablename__ = "linked_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    access_token = Column(EncryptedString, nullable=False)
    item_id = Column(String, unique=True, nullable=False, index=True)  # maps Plaid webhooks → account
    institution_name = Column(String, nullable=True)
    # Cursor for Plaid /transactions/sync — NULL means no sync has run yet.
    sync_cursor = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BalanceSnapshot(Base):
    """One net-worth data point per user per day, written when fresh balances
    are fetched from Plaid (see /plaid/balances)."""
    __tablename__ = "balance_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_snapshot_user_date"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    total_available = Column(Float, nullable=False)
    total_current = Column(Float, nullable=False)


class BudgetAlert(Base):
    """Tracks which budget-threshold emails were already sent, so each alert
    (per user, category, month, threshold) goes out exactly once."""
    __tablename__ = "budget_alerts"
    __table_args__ = (UniqueConstraint("user_id", "category", "month", "threshold", name="uq_budget_alert"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, nullable=False)   # display name e.g. "Dining"
    month = Column(String, nullable=False)      # "YYYY-MM"
    threshold = Column(Integer, nullable=False)  # 90 or 100 (percent)
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


class DigestLog(Base):
    """Records which month-end digest emails were sent (one per user per month)."""
    __tablename__ = "digest_log"
    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_digest_user_month"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month = Column(String, nullable=False)  # the digested month, "YYYY-MM"
    created_at = Column(DateTime, default=datetime.utcnow)


class SavingsGoal(Base):
    """A savings target. Progress = net cash flow (income − spend, transfers
    excluded) accumulated since the goal was created, floored at zero."""
    __tablename__ = "savings_goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    target_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plaid_transaction_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    merchant_name = Column(String, nullable=True)  # Plaid's cleaned merchant name
    logo_url = Column(String, nullable=True)       # merchant logo from Plaid enrichment
    # Which bank account this came from (denormalized for display/filtering)
    plaid_account_id = Column(String, nullable=True)
    account_name = Column(String, nullable=True)      # e.g. "Chequing ••1234"
    institution_name = Column(String, nullable=True)  # e.g. "Tangerine - Personal"
    amount = Column(Float, nullable=False)
    date = Column(DateTime, nullable=False)
    category = Column(String, nullable=True)
    ml_category = Column(String, nullable=True)
    # True when the user manually set the category — ML won't overwrite it, and
    # it's used as per-user training feedback for same-named transactions.
    category_overridden = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    is_anomaly = Column(Boolean, default=False)
    anomaly_score = Column(Float, nullable=True)
    # User feedback: "this is expected" — ML re-runs won't re-flag it.
    anomaly_dismissed = Column(Boolean, nullable=False, default=False, server_default=text("false"))
