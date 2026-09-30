"""Dépendances FastAPI : BD, Redis, Elasticsearch, utilisateur connecté et contrôle des rôles."""
from dataclasses import dataclass
from typing import Annotated

import jwt
import redis
from elasticsearch import Elasticsearch
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.redis_client import get_redis
from app.core.security import decode_access_token
from app.repositories.search import get_es

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

Db = Annotated[Session, Depends(get_db)]
Redis = Annotated[redis.Redis, Depends(get_redis)]
Es = Annotated[Elasticsearch, Depends(get_es)]


def clean_text(value: str | None, field: str, max_length: int, required: bool = True) -> str | None:
    """Validation des champs texte envoyés en multipart (formulaires avec fichier)."""
    if value is None:
        if required:
            raise AppError(422, "VALIDATION_ERROR", "Invalid data", fields={field: "Field required"})
        return None
    value = value.strip()
    if not value or len(value) > max_length:
        raise AppError(422, "VALIDATION_ERROR", "Invalid data",
                       fields={field: f"Must contain between 1 and {max_length} characters"})
    return value


@dataclass(frozen=True)
class CurrentUser:
    id: int
    role: str
    artist_id: int | None


def get_current_user(request: Request) -> CurrentUser:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise AppError(401, "AUTH_REQUIRED", "Authentication required")
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise AppError(401, "TOKEN_EXPIRED", "Session expired")
    except jwt.InvalidTokenError:
        raise AppError(401, "AUTH_REQUIRED", "Authentication required")
    return CurrentUser(id=int(payload["sub"]), role=payload["role"], artist_id=payload.get("aid"))


def require_role(*roles: str):
    """À placer sur chaque route : vérifie le rôle côté serveur."""

    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise AppError(403, "FORBIDDEN", "Access denied")
        return user

    return checker


def require_artist(user: CurrentUser = Depends(require_role("artist"))) -> CurrentUser:
    if user.artist_id is None:
        raise AppError(403, "FORBIDDEN", "Access denied")
    return user
