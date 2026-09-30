"""Cache Redis : playlist à la une (identique pour tous) et recherches fréquentes."""
import json

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.redis_client import HOME_CACHE
from app.core.security import sha256
from app.models import FEATURED_PLAYLIST_KEY, AppSetting, PlaylistTrack
from app.repositories import catalog, search
from app.schemas import TrackOut


def featured_playlist_id(db: Session) -> int | None:
    value = db.scalar(select(AppSetting.value).where(AppSetting.key == FEATURED_PLAYLIST_KEY))
    return int(value) if value else None


def featured_tracks(db: Session, r: redis.Redis) -> list[TrackOut]:
    cached = r.get(HOME_CACHE)
    if cached is not None:
        return [TrackOut.model_validate(t) for t in json.loads(cached)]
    playlist_id = featured_playlist_id(db)
    ids = []
    if playlist_id:
        ids = list(db.scalars(
            select(PlaylistTrack.track_id)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .order_by(PlaylistTrack.position)
        ))
    tracks = catalog.visible_tracks_by_ids(db, ids)
    r.set(HOME_CACHE, json.dumps([t.model_dump(mode="json") for t in tracks]))
    return tracks


def invalidate_home(r: redis.Redis) -> None:
    r.delete(HOME_CACHE)


def search_results(es, r: redis.Redis, q: str) -> dict:
    """Résultats bruts Elasticsearch, mis en cache 30–60 s."""
    key = "cache:search:" + sha256(q.lower())
    cached = r.get(key)
    if cached is not None:
        return json.loads(cached)
    s = get_settings()
    results = search.msearch(es, q, s.search_results_per_section)
    r.set(key, json.dumps(results), ex=s.search_cache_ttl_s)
    return results
