"""Emails : l'API les met en file dans Redis, le worker les envoie (jamais pendant la requête HTTP)."""
import json

import redis

from app.core.config import get_settings
from app.core.redis_client import MAIL_QUEUE


def queue_email(r: redis.Redis, to: str, subject: str, body: str) -> None:
    r.rpush(MAIL_QUEUE, json.dumps({"to": to, "subject": subject, "body": body}))


def send_verification(r: redis.Redis, to: str, username: str, token: str) -> None:
    link = f"{get_settings().public_url}/#/verify?token={token}"
    queue_email(
        r, to, "MusicApp - Verify your email address",
        f"Hello {username},\n\nClick on this link to verify your account:\n{link}\n\n"
        "This link expires in 24 hours.",
    )


def send_reset(r: redis.Redis, to: str, username: str, token: str) -> None:
    link = f"{get_settings().public_url}/#/reset-password?token={token}"
    queue_email(
        r, to, "MusicApp - Reset your password",
        f"Hello {username},\n\nClick on this link to choose a new password:\n{link}\n\n"
        "This link expires in 24 hours. If you did not ask for it, ignore this email.",
    )


def send_artist_approved(r: redis.Redis, to: str, name: str) -> None:
    queue_email(
        r, to, "MusicApp - Your artist account is approved",
        f"Hello {name},\n\nYour artist account has been approved. You can now log in:\n"
        f"{get_settings().public_url}/#/login",
    )


def send_artist_rejected(r: redis.Redis, to: str, name: str, reason: str) -> None:
    queue_email(
        r, to, "MusicApp - Your artist account was refused",
        f"Hello {name},\n\nYour artist account has been refused.\n\nReason: {reason}",
    )
