from sqlalchemy import Column, String, Float, DateTime, Boolean, ForeignKey, Integer, text
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
    totp_secret = Column(String, nullable=True)
    totp_enabled = Column(Boolean, default=False)
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    username = Column(String, nullable=True)
    profile_picture = Column(String, nullable=True)
    # Bumped to invalidate all of a user's existing JWTs (password change/reset).
    token_version = Column(Integer, nullable=False, default=0, server_default=text("0"))
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
    is_anomaly = Column(Boolean, default=False)
    anomaly_score = Column(Float, nullable=True)
