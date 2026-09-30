"""Compteur d'écoutes : INCR dans Redis, écrit en base par lot par le worker
(pas d'UPDATE MySQL à chaque écoute)."""
import time

import redis

from app.core.redis_client import HISTORY_LIST, PLAYS_HASH


def record_play(r: redis.Redis, user_id: int, track_id: int) -> None:
    pipe = r.pipeline()
    pipe.hincrby(PLAYS_HASH, str(track_id), 1)
    pipe.rpush(HISTORY_LIST, f"{user_id}:{track_id}:{int(time.time())}")
    pipe.execute()
