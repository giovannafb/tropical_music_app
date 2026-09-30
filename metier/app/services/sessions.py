"""Sessions : JWT d'accès court + refresh token stocké (haché) dans Redis.
L'API ne garde aucun état en mémoire : elle peut être dupliquée."""
import redis
from fastapi import Response

from app.core.config import get_settings
from app.core.deps import ACCESS_COOKIE, REFRESH_COOKIE
from app.core.security import create_access_token, new_token, sha256

REFRESH_PATH = "/api/auth"


def _refresh_key(token_hash: str) -> str:
    return f"refresh:{token_hash}"


def _user_sessions_key(user_id: int) -> str:
    return f"user_sessions:{user_id}"


def _set_cookie(response: Response, name: str, value: str, max_age: int, path: str) -> None:
    response.set_cookie(
        name, value, max_age=max_age, path=path,
        httponly=True, secure=get_settings().cookie_secure, samesite="strict",
    )


def set_access_cookie(response: Response, user_id: int, role: str, artist_id: int | None) -> None:
    s = get_settings()
    _set_cookie(response, ACCESS_COOKIE, create_access_token(user_id, role, artist_id), s.access_ttl_s, "/api")


def open_session(r: redis.Redis, response: Response, user_id: int, role: str, artist_id: int | None) -> None:
    s = get_settings()
    refresh = new_token()
    token_hash = sha256(refresh)
    pipe = r.pipeline()
    pipe.set(_refresh_key(token_hash), str(user_id), ex=s.refresh_ttl_s)
    pipe.sadd(_user_sessions_key(user_id), token_hash)
    pipe.expire(_user_sessions_key(user_id), s.refresh_ttl_s)
    pipe.execute()
    set_access_cookie(response, user_id, role, artist_id)
    _set_cookie(response, REFRESH_COOKIE, refresh, s.refresh_ttl_s, REFRESH_PATH)


def consume_refresh(r: redis.Redis, refresh: str | None) -> int | None:
    """Valide et invalide le refresh token (rotation) ; renvoie l'id utilisateur."""
    if not refresh:
        return None
    token_hash = sha256(refresh)
    user_id = r.getdel(_refresh_key(token_hash))
    if user_id is None:
        return None
    r.srem(_user_sessions_key(int(user_id)), token_hash)
    return int(user_id)


def close_session(r: redis.Redis, response: Response, refresh: str | None) -> None:
    consume_refresh(r, refresh)
    clear_cookies(response)


def clear_cookies(response: Response) -> None:
    secure = get_settings().cookie_secure
    response.delete_cookie(ACCESS_COOKIE, path="/api", httponly=True, secure=secure, samesite="strict")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, httponly=True, secure=secure, samesite="strict")


def revoke_all(r: redis.Redis, user_id: int) -> None:
    """Déconnecte toutes les sessions d'un utilisateur (ex. changement de mot de passe)."""
    key = _user_sessions_key(user_id)
    hashes = r.smembers(key)
    pipe = r.pipeline()
    for token_hash in hashes:
        pipe.delete(_refresh_key(token_hash))
    pipe.delete(key)
    pipe.execute()
