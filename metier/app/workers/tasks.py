"""Tâches du worker (synchrones, appelées par workers/main.py)."""
import json
from datetime import UTC, datetime

import redis
from elasticsearch import Elasticsearch
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.redis_client import HISTORY_LIST, MAIL_QUEUE, PLAYS_HASH
from app.models import ListeningHistory, SearchOutbox, Track, User
from app.repositories import outbox, search

PLAYS_FLUSHING = "plays:flushing"
HISTORY_BATCH = 1000


def process_outbox(db: Session, es: Elasticsearch, limit: int = 500) -> int:
    """Lit la table outbox, indexe dans ES via _bulk, puis marque les lignes traitées."""
    rows = list(db.scalars(
        select(SearchOutbox).where(SearchOutbox.processed_at.is_(None)).order_by(SearchOutbox.id).limit(limit)
    ))
    if not rows:
        return 0
    latest: dict[tuple[str, int], str] = {}
    for row in rows:
        latest[(row.entity, row.entity_id)] = row.action
    operations: list[dict] = []
    for (entity, entity_id), action in latest.items():
        operations += search.bulk_actions_for(db, entity, entity_id, action)
    search.bulk(es, operations)
    now = utcnow()
    for row in rows:
        row.processed_at = now
    db.commit()
    return len(rows)


def flush_play_counts(db: Session, r: redis.Redis) -> int:
    """Écrit en base, par lot, les écoutes comptées dans Redis."""
    if not r.exists(PLAYS_FLUSHING):
        if not r.exists(PLAYS_HASH):
            return 0
        r.rename(PLAYS_HASH, PLAYS_FLUSHING)   # atomique : les nouvelles écoutes repartent de zéro
    counts = {int(k): int(v) for k, v in r.hgetall(PLAYS_FLUSHING).items()}
    for track_id, n in counts.items():
        db.execute(update(Track).where(Track.id == track_id).values(play_count=Track.play_count + n))
    outbox.add_many(db, "track", counts.keys())   # mise à jour périodique de play_count dans ES
    db.commit()
    r.delete(PLAYS_FLUSHING)
    return len(counts)


def flush_history(db: Session, r: redis.Redis) -> int:
    pipe = r.pipeline()
    pipe.lrange(HISTORY_LIST, 0, HISTORY_BATCH - 1)
    pipe.ltrim(HISTORY_LIST, HISTORY_BATCH, -1)
    items, _ = pipe.execute()
    if not items:
        return 0
    entries = []
    for item in items:
        user_id, track_id, ts = (int(x) for x in item.split(":"))
        entries.append((user_id, track_id, datetime.fromtimestamp(ts, UTC).replace(tzinfo=None)))
    # Ignore les écoutes d'un titre ou d'un compte supprimé entre-temps
    track_ids = set(db.scalars(select(Track.id).where(Track.id.in_({e[1] for e in entries}))))
    user_ids = set(db.scalars(select(User.id).where(User.id.in_({e[0] for e in entries}))))
    try:
        db.add_all(
            ListeningHistory(user_id=u, track_id=t, played_at=p)
            for u, t, p in entries if u in user_ids and t in track_ids
        )
        db.commit()
    except Exception:
        db.rollback()
        r.rpush(HISTORY_LIST, *items)   # on réessaiera au prochain passage
        raise
    return len(entries)


def pop_email(r: redis.Redis, timeout: int = 5) -> dict | None:
    item = r.blpop([MAIL_QUEUE], timeout=timeout)
    return json.loads(item[1]) if item else None


def requeue_email(r: redis.Redis, mail: dict) -> None:
    r.rpush(MAIL_QUEUE, json.dumps(mail))
