import io
import base64
import pyotp
import qrcode

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from zxcvbn import zxcvbn

from auth import (
    SECRET_KEY, ALGORITHM,
    hash_password, verify_password,
    create_access_token, create_refresh_token, create_totp_challenge_token,
    generate_verification_token, get_current_user,
    set_refresh_cookie, clear_refresh_cookie,
)
from database import get_db
from email_utils import send_verification_email, send_password_reset_email
from models import User

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

# Valid bcrypt hash used to equalize login timing when the email doesn't exist.
_DUMMY_HASH = "$2b$12$tXLlfUbtlsQZHT6jlHiQ/.r0Q0H0n1rxv5WXxoD4uoEX5FmTQWfiq"


# ── Schemas ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class VerifyEmailRequest(BaseModel):
    token: str

class TOTPVerifyRequest(BaseModel):
    challenge_token: str
    code: str

class TOTPConfirmRequest(BaseModel):
    code: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    password: str


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Password strength — require score ≥ 2 (zxcvbn scale 0–4)
    strength = zxcvbn(body.password, user_inputs=[body.email])
    if strength["score"] < 2:
        suggestion = strength["feedback"]["suggestions"][0] if strength["feedback"]["suggestions"] else "Choose a stronger password."
        raise HTTPException(status_code=422, detail=f"Password too weak. {suggestion}")

    verification_token = generate_verification_token()
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        verification_token=verification_token,
    )
    db.add(user)
    db.commit()

    try:
        send_verification_email(body.email, verification_token)
    except Exception:
        pass

    return {"message": "Account created. Check your email to verify your address."}


# ── Verify email ──────────────────────────────────────────────────────────────

@router.post("/verify-email")
@limiter.limit("10/minute")
def verify_email(request: Request, body: VerifyEmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == body.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user.is_verified = True
    user.verification_token = None
    db.commit()
    return {"message": "Email verified. You can now log in."}


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    # Always run verify_password even if user not found to prevent timing attacks.
    # Must be a *valid* bcrypt hash or verify_password raises on the no-user path.
    password_ok = verify_password(body.password, user.hashed_password if user else _DUMMY_HASH)

    if not user or not password_ok:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in")

    if user.totp_enabled:
        return {
            "totp_required": True,
            "challenge_token": create_totp_challenge_token(str(user.id)),
        }

    set_refresh_cookie(response, create_refresh_token(str(user.id), user.token_version))
    return {
        "totp_required": False,
        "totp_enabled": user.totp_enabled,
        "is_demo": user.is_demo,
        "access_token": create_access_token(str(user.id), user.token_version),
        "token_type": "bearer",
    }


# ── TOTP login challenge ──────────────────────────────────────────────────────

@router.post("/verify-totp-login")
@limiter.limit("10/minute")
def verify_totp_login(request: Request, body: TOTPVerifyRequest, response: Response, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Invalid challenge token")
    try:
        payload = jwt.decode(body.challenge_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "totp_challenge":
            raise credentials_exception
        user_id = payload.get("sub")
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.totp_secret:
        raise credentials_exception

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid authenticator code")

    set_refresh_cookie(response, create_refresh_token(str(user.id), user.token_version))
    return {
        "access_token": create_access_token(str(user.id), user.token_version),
        "token_type": "bearer",
    }


# ── Refresh token ─────────────────────────────────────────────────────────────

@router.post("/refresh")
@limiter.limit("30/minute")
def refresh_token(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(status_code=401, detail="Invalid refresh token")
    if not refresh_token:
        raise credentials_exception
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise credentials_exception
        user_id = payload.get("sub")
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if not user or payload.get("tv") != user.token_version:
        raise credentials_exception

    return {
        "access_token": create_access_token(str(user.id), user.token_version),
        "token_type": "bearer",
    }


# ── TOTP setup ────────────────────────────────────────────────────────────────

@router.post("/setup-totp")
@limiter.limit("10/minute")
def setup_totp(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    secret = pyotp.random_base32()
    current_user.totp_secret = secret
    db.commit()

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.email, issuer_name="Finance App")

    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {"secret": secret, "qr_code": f"data:image/png;base64,{qr_b64}"}


@router.post("/confirm-totp")
@limiter.limit("10/minute")
def confirm_totp(
    request: Request,
    body: TOTPConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Run /auth/setup-totp first")

    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid code — try again")

    current_user.totp_enabled = True
    db.commit()
    return {"message": "Two-factor authentication enabled"}


class DisableTOTPRequest(BaseModel):
    password: str

@router.delete("/disable-totp")
@limiter.limit("5/minute")
def disable_totp(
    request: Request,
    body: DisableTOTPRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Re-authenticate: a stolen access token alone must not be able to weaken 2FA.
    if not verify_password(body.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Password is incorrect")
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.commit()
    return {"message": "Two-factor authentication disabled"}


# ── Forgot / reset password ───────────────────────────────────────────────────

@router.post("/forgot-password")
@limiter.limit("3/minute")
def forgot_password(request: Request, body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    from datetime import datetime, timedelta
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        return {"message": "If that email exists you'll receive a reset link shortly."}

    token = generate_verification_token()
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    try:
        send_password_reset_email(body.email, token)
    except Exception:
        pass

    return {"message": "If that email exists you'll receive a reset link shortly."}


@router.post("/reset-password")
@limiter.limit("5/minute")
def reset_password(request: Request, body: ResetPasswordRequest, db: Session = Depends(get_db)):
    from datetime import datetime

    strength = zxcvbn(body.password)
    if strength["score"] < 2:
        suggestion = strength["feedback"]["suggestions"][0] if strength["feedback"]["suggestions"] else "Choose a stronger password."
        raise HTTPException(status_code=422, detail=f"Password too weak. {suggestion}")

    user = db.query(User).filter(User.reset_token == body.token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    user.hashed_password = hash_password(body.password)
    user.reset_token = None
    user.reset_token_expires = None
    user.token_version += 1  # revoke any existing sessions
    db.commit()
    return {"message": "Password updated. You can now log in."}


# ── Change password ───────────────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/change-password")
@limiter.limit("5/minute")
def change_password(
    request: Request,
    body: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Not allowed for the demo account.")
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    strength = zxcvbn(body.new_password, user_inputs=[current_user.email])
    if strength["score"] < 2:
        suggestion = strength["feedback"]["suggestions"][0] if strength["feedback"]["suggestions"] else "Choose a stronger password."
        raise HTTPException(status_code=422, detail=f"Password too weak. {suggestion}")
    current_user.hashed_password = hash_password(body.new_password)
    current_user.token_version += 1  # revoke all other sessions
    db.commit()
    # Re-issue tokens for the current device so this session stays logged in.
    set_refresh_cookie(response, create_refresh_token(str(current_user.id), current_user.token_version))
    return {
        "message": "Password updated successfully.",
        "access_token": create_access_token(str(current_user.id), current_user.token_version),
        "token_type": "bearer",
    }


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(response: Response):
    """Clear the refresh-token cookie. (Access token is in-memory and expires on its own.)"""
    clear_refresh_cookie(response)
    return {"message": "Logged out."}


# ── Delete account ─────────────────────────────────────────────────────────────

class DeleteAccountRequest(BaseModel):
    password: str

@router.delete("/delete-account")
@limiter.limit("3/minute")
def delete_account(
    request: Request,
    body: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Not allowed for the demo account.")
    # Re-authenticate before an irreversible, destructive action.
    if not verify_password(body.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Password is incorrect")
    from models import Transaction
    db.query(Transaction).filter(Transaction.user_id == current_user.id).delete()
    db.delete(current_user)
    db.commit()
    return {"message": "Account deleted."}


# ── Update profile ─────────────────────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    username: str | None = None
    profile_picture: str | None = None

@router.patch("/profile")
@limiter.limit("10/minute")
def update_profile(
    request: Request,
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.username is not None:
        username = body.username.strip()
        if len(username) < 2:
            raise HTTPException(status_code=422, detail="Username must be at least 2 characters")
        if len(username) > 30:
            raise HTTPException(status_code=422, detail="Username must be 30 characters or fewer")
        existing = db.query(User).filter(User.username == username, User.id != current_user.id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")
        current_user.username = username
    if body.profile_picture is not None:
        current_user.profile_picture = body.profile_picture
    db.commit()
    return {"message": "Profile updated."}


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "totp_enabled": current_user.totp_enabled,
        "username": current_user.username,
        "profile_picture": current_user.profile_picture,
        "is_demo": current_user.is_demo,
    }
