"""Inscription, connexion, vérification d'email, mot de passe oublié."""
from datetime import timedelta

import redis
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import AppError
from app.core.security import hash_password, new_token, sha256, verify_password
from app.models import Artist, EmailToken, User
from app.services import emails, sessions


def _check_unique(db: Session, username: str, email: str) -> None:
    if db.scalar(select(User.id).where(User.username == username)):
        raise AppError(409, "USERNAME_TAKEN", "This username is already taken")
    if db.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, "EMAIL_TAKEN", "An account already exists with this email")


def _create_email_token(db: Session, user_id: int, purpose: str) -> str:
    token = new_token()
    db.add(EmailToken(
        user_id=user_id,
        token_hash=sha256(token),
        purpose=purpose,
        expires_at=utcnow() + timedelta(seconds=get_settings().email_token_ttl_s),
    ))
    return token


def _create_user(db: Session, username: str, email: str, password: str, role: str) -> User:
    _check_unique(db, username, email)
    user = User(username=username, email=email.lower(), password_hash=hash_password(password), role=role)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "USERNAME_TAKEN", "This username or email is already taken")
    return user


def register_user(db: Session, r: redis.Redis, username: str, email: str, password: str) -> User:
    user = _create_user(db, username, email, password, "user")
    token = _create_email_token(db, user.id, "verify")
    db.commit()
    emails.send_verification(r, user.email, user.username, token)
    return user


def register_artist(
    db: Session, r: redis.Redis, username: str, email: str, password: str, artist_name: str, bio: str
) -> User:
    user = _create_user(db, username, email, password, "artist")
    db.add(Artist(user_id=user.id, name=artist_name, bio=bio, status="pending"))
    token = _create_email_token(db, user.id, "verify")
    db.commit()
    emails.send_verification(r, user.email, user.username, token)
    return user


def authenticate(db: Session, login: str, password: str) -> tuple[User, Artist | None]:
    login = login.strip()
    user = db.scalar(select(User).where(or_(User.username == login, User.email == login.lower())))
    if not user or not verify_password(user.password_hash, password):
        raise AppError(401, "INVALID_CREDENTIALS", "Wrong username or password")
    if not user.is_verified:
        raise AppError(403, "EMAIL_NOT_VERIFIED", "Account not verified")
    artist = None
    if user.role == "artist":
        artist = db.scalar(select(Artist).where(Artist.user_id == user.id))
        if artist is None or artist.status == "pending":
            raise AppError(403, "ARTIST_PENDING", "Your artist account is waiting for validation")
        if artist.status == "rejected":
            raise AppError(403, "ARTIST_REJECTED", "Your artist account was refused",
                           reason=artist.rejection_reason or "")
    return user, artist


def _use_email_token(db: Session, token: str, purpose: str) -> EmailToken:
    row = db.scalar(select(EmailToken).where(EmailToken.token_hash == sha256(token), EmailToken.purpose == purpose))
    if not row or row.used_at is not None or row.expires_at < utcnow():
        raise AppError(400, "INVALID_TOKEN", "This link is invalid or has expired")
    row.used_at = utcnow()
    return row


def verify_email(db: Session, token: str) -> User:
    row = _use_email_token(db, token, "verify")
    user = db.get(User, row.user_id)
    user.is_verified = True
    db.commit()
    return user


def _rate_limited(r: redis.Redis, key: str) -> bool:
    """Vrai si une action identique a eu lieu il y a moins d'une minute."""
    return not r.set(key, "1", nx=True, ex=get_settings().resend_interval_s)


def resend_verification(db: Session, r: redis.Redis, email: str) -> None:
    """Répond toujours de la même façon (ne révèle pas si le compte existe)."""
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or user.is_verified:
        return
    if _rate_limited(r, f"resend:verify:{user.id}"):
        raise AppError(429, "TOO_MANY_REQUESTS", "Please wait a minute before asking again")
    token = _create_email_token(db, user.id, "verify")
    db.commit()
    emails.send_verification(r, user.email, user.username, token)


def forgot_password(db: Session, r: redis.Redis, email: str) -> None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or _rate_limited(r, f"resend:reset:{user.id}"):
        return
    token = _create_email_token(db, user.id, "reset")
    db.commit()
    emails.send_reset(r, user.email, user.username, token)


def reset_password(db: Session, r: redis.Redis, token: str, password: str) -> None:
    row = _use_email_token(db, token, "reset")
    user = db.get(User, row.user_id)
    user.password_hash = hash_password(password)
    db.commit()
    sessions.revoke_all(r, user.id)


def change_password(db: Session, r: redis.Redis, user_id: int, old_password: str, new_password: str) -> None:
    user = db.get(User, user_id)
    if not verify_password(user.password_hash, old_password):
        raise AppError(400, "WRONG_PASSWORD", "Old password is incorrect")
    user.password_hash = hash_password(new_password)
    db.commit()
    sessions.revoke_all(r, user.id)


def change_username(db: Session, user_id: int, username: str) -> User:
    user = db.get(User, user_id)
    if username != user.username:
        if db.scalar(select(User.id).where(User.username == username, User.id != user_id)):
            raise AppError(409, "USERNAME_TAKEN", "This username is already taken")
        user.username = username
        db.commit()
    return user
