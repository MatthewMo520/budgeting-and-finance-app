import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import User

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "change-me-in-production":
    raise RuntimeError(
        "JWT_SECRET_KEY must be set to a strong secret before the app can start "
        "(generate one with: openssl rand -hex 32)."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# ── Refresh-token cookie config ───────────────────────────────────────────────
# The refresh token lives in an httpOnly cookie (never readable by JS) so an XSS
# can't steal long-lived credentials. Flags are env-driven so local dev (http,
# same-origin via Vite proxy) and prod (https, cross-site) can both work:
#   local:  COOKIE_SECURE=false COOKIE_SAMESITE=lax
#   prod:   COOKIE_SECURE=true  COOKIE_SAMESITE=none   (cross-site needs none+secure)
REFRESH_COOKIE_NAME = "refresh_token"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").lower()


def set_refresh_cookie(response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str, token_version: int = 0) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "access", "tv": token_version}, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str, token_version: int = 0) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "refresh", "tv": token_version}, SECRET_KEY, algorithm=ALGORITHM)


def create_totp_challenge_token(user_id: str) -> str:
    """Short-lived token issued after password check but before TOTP verification."""
    expire = datetime.utcnow() + timedelta(minutes=5)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "totp_challenge"}, SECRET_KEY, algorithm=ALGORITHM)


def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Deterministic hash for storing email-verification / password-reset tokens
    at rest. These are bearer secrets — a DB leak of raw tokens would allow
    account takeover. We store sha256(token) and look up by the same hash."""
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise credentials_exception
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise credentials_exception
    # Token version check — incrementing user.token_version revokes all prior
    # tokens (e.g. after a password change).
    if payload.get("tv") != user.token_version:
        raise credentials_exception
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified")
    return user
