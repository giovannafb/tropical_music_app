"""Client Redis : cache, compteurs, sessions (refresh tokens), file d'emails."""
from functools import lru_cache

import redis

from app.core.config import get_settings

# Clés utilisées dans Redis
PLAYS_HASH = "plays"                 # compteur d'écoutes : track_id -> n
HISTORY_LIST = "history"             # écoutes à écrire dans listening_history
MAIL_QUEUE = "mail:queue"            # emails à envoyer par le worker
HOME_CACHE = "cache:home"            # titres de la playlist à la une


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
