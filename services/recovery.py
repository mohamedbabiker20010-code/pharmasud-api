"""Email password recovery with hash-only, expiring, single-use tokens."""

from datetime import datetime, timedelta
import hashlib
import secrets
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_password_hash
from models import PasswordResetToken, User
from services.mail import MailTransport, reset_message

RESET_TTL_MINUTES = 20


class ResetError(RuntimeError):
    pass


def hash_reset_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def request_password_reset(db: Session, *, email: str, transport: MailTransport, now=None) -> None:
    current = now or datetime.utcnow()
    user = db.query(User).filter(func.lower(User.email) == email.strip().lower()).one_or_none()
    if user is None or not user.is_active or not user.email:
        return
    for token in db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.revoked_at.is_(None),
    ):
        token.revoked_at = current
    secret = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        id=uuid.uuid4(), user_id=user.id, token_hash=hash_reset_secret(secret),
        expires_at=current + timedelta(minutes=RESET_TTL_MINUTES),
    ))
    db.flush()
    transport.send(reset_message(recipient=user.email, secret=secret, expires_minutes=RESET_TTL_MINUTES))


def reset_password(db: Session, *, secret: str, password: str, now=None) -> User:
    current = now or datetime.utcnow()
    if len(password) < 12 or len(password.encode()) > 72:
        raise ResetError("Reset link is invalid or expired")
    token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == hash_reset_secret(secret)
    ).with_for_update().one_or_none()
    if token is None or token.used_at or token.revoked_at or token.expires_at <= current:
        raise ResetError("Reset link is invalid or expired")
    user = db.query(User).filter(User.id == token.user_id).with_for_update().one_or_none()
    if user is None or not user.is_active or not user.email:
        raise ResetError("Reset link is invalid or expired")
    user.password_hash = get_password_hash(password)
    user.auth_version += 1
    token.used_at = current
    for other in db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.id != token.id,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.revoked_at.is_(None),
    ):
        other.revoked_at = current
    db.flush()
    return user
