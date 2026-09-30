"""Configuration lue dans les variables d'environnement (fichier .env non versionné)."""
import os
from dataclasses import dataclass
from functools import lru_cache


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Variable d'environnement manquante : {name}")
    return value


def _bool(name: str, default: str) -> bool:
    return _env(name, default).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    es_hosts: list[str]
    jwt_secret: str
    public_url: str
    media_root: str
    cookie_secure: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_starttls: bool
    mail_from: str

    # Règles fixées avec le porteur du projet
    access_ttl_s: int = 15 * 60            # JWT court (~15 min)
    refresh_ttl_s: int = 7 * 24 * 3600     # session de 7 jours
    email_token_ttl_s: int = 24 * 3600     # tokens email : 24 h
    resend_interval_s: int = 60            # renvoi d'email : 1 par minute
    password_min_length: int = 8
    max_audio_bytes: int = 50 * 1024 * 1024
    max_cover_bytes: int = 10 * 1024 * 1024
    search_results_per_section: int = 10
    search_cache_ttl_s: int = 45           # cache court des recherches (30–60 s)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=_env("DATABASE_URL"),
        redis_url=_env("REDIS_URL", "redis://redis:6379/0"),
        es_hosts=[h.strip() for h in _env("ES_HOSTS", "http://es01:9200,http://es02:9200,http://es03:9200").split(",") if h.strip()],
        jwt_secret=_env("JWT_SECRET"),
        public_url=_env("PUBLIC_URL", "http://localhost").rstrip("/"),
        media_root=_env("MEDIA_ROOT", "/data"),
        cookie_secure=_bool("COOKIE_SECURE", "true"),
        smtp_host=_env("SMTP_HOST", "mailpit"),
        smtp_port=int(_env("SMTP_PORT", "1025")),
        smtp_user=_env("SMTP_USER", ""),
        smtp_password=_env("SMTP_PASSWORD", ""),
        smtp_starttls=_bool("SMTP_STARTTLS", "false"),
        mail_from=_env("MAIL_FROM", "MusicApp <no-reply@musicapp.local>"),
    )
