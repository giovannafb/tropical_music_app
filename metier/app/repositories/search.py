"""Elasticsearch : index tracks / albums / artists (accès par alias), documents et requêtes.

Seuls les contenus publiés d'artistes validés sont indexés.
MySQL reste la source de vérité ; ES n'est qu'une copie pour la recherche.
"""
import os
import time
from functools import lru_cache

from elasticsearch import Elasticsearch, NotFoundError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Album, Artist, Track

ALIASES = ("tracks", "albums", "artists")


def index_settings() -> dict:
    return {
        "number_of_shards": 1,
        "number_of_replicas": int(os.environ.get("ES_REPLICAS", "2")),
        "analysis": {
            "analyzer": {
                "folding": {"tokenizer": "standard", "filter": ["lowercase", "asciifolding"]}
            }
        },
    }


_SAYT = {"type": "search_as_you_type", "analyzer": "folding"}
_KEYWORD_STORED = {"type": "keyword", "index": False}

MAPPINGS = {
    "tracks": {
        "properties": {
            "title": _SAYT,
            "artist_name": _SAYT,
            "album_title": {"type": "text", "analyzer": "folding"},
            "duration_s": {"type": "integer"},
            "play_count": {"type": "integer"},
            "release_date": {"type": "date"},
            "artist_id": {"type": "integer", "index": False},
            "album_id": {"type": "integer", "index": False},
            "cover_path": _KEYWORD_STORED,
        }
    },
    "albums": {
        "properties": {
            "title": _SAYT,
            "artist_name": _SAYT,
            "artist_id": {"type": "integer", "index": False},
            "cover_path": _KEYWORD_STORED,
            "duration_s": {"type": "integer"},
            "track_count": {"type": "integer"},
            "release_date": {"type": "date"},
        }
    },
    "artists": {
        "properties": {
            "name": _SAYT,
            "bio": {"type": "text", "index": False},
        }
    },
}

# Champs interrogés et pondération (title^3, artist_name^2, album_title)
QUERY_FIELDS = {
    "tracks": [
        "title^3", "title._2gram^3", "title._3gram^3",
        "artist_name^2", "artist_name._2gram^2", "artist_name._3gram^2",
        "album_title",
    ],
    "albums": [
        "title^3", "title._2gram^3", "title._3gram^3",
        "artist_name^2", "artist_name._2gram^2", "artist_name._3gram^2",
    ],
    "artists": ["name^3", "name._2gram^3", "name._3gram^3"],
}


@lru_cache
def get_es() -> Elasticsearch:
    # Le client reçoit les 3 nœuds et répartit les requêtes lui-même
    return Elasticsearch(get_settings().es_hosts, request_timeout=10, retry_on_timeout=True, max_retries=2)


# ---------- Index et alias ----------

def create_index(es: Elasticsearch, alias: str, suffix: str | None = None) -> str:
    name = f"{alias}_{suffix or int(time.time())}"
    es.indices.create(index=name, settings=index_settings(), mappings=MAPPINGS[alias])
    return name


def ensure_indices(es: Elasticsearch) -> None:
    """Crée chaque index + alias s'il n'existe pas encore."""
    for alias in ALIASES:
        if not es.indices.exists_alias(name=alias):
            name = create_index(es, alias, "v1")
            es.indices.put_alias(index=name, name=alias)


def swap_alias(es: Elasticsearch, alias: str, new_index: str) -> None:
    """Bascule l'alias vers le nouvel index sans coupure, puis supprime les anciens."""
    old = list(es.indices.get_alias(name=alias).keys()) if es.indices.exists_alias(name=alias) else []
    actions = [{"remove": {"index": i, "alias": alias}} for i in old]
    actions.append({"add": {"index": new_index, "alias": alias}})
    es.indices.update_aliases(actions=actions)
    for i in old:
        if i != new_index:
            es.indices.delete(index=i)


# ---------- Documents (construits depuis MySQL) ----------

def _visible(album: Album | None, artist: Artist | None) -> bool:
    return bool(album and artist and album.status == "published" and artist.status == "approved")


def track_doc(db: Session, track_id: int) -> dict | None:
    row = db.execute(
        select(Track, Album, Artist)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Album.artist_id == Artist.id)
        .where(Track.id == track_id)
    ).first()
    if not row or not _visible(row[1], row[2]):
        return None
    track, album, artist = row
    return {
        "title": track.title,
        "artist_name": artist.name,
        "album_title": album.title,
        "duration_s": track.duration_s,
        "play_count": track.play_count,
        "release_date": album.release_date.isoformat() if album.release_date else None,
        "artist_id": artist.id,
        "album_id": album.id,
        "cover_path": album.cover_path,
    }


def album_doc(db: Session, album_id: int) -> dict | None:
    row = db.execute(select(Album, Artist).join(Artist, Album.artist_id == Artist.id).where(Album.id == album_id)).first()
    if not row or not _visible(*row):
        return None
    album, artist = row
    count, total = db.execute(
        select(func.count(Track.id), func.coalesce(func.sum(Track.duration_s), 0)).where(Track.album_id == album.id)
    ).one()
    return {
        "title": album.title,
        "artist_name": artist.name,
        "artist_id": artist.id,
        "cover_path": album.cover_path,
        "duration_s": int(total),
        "track_count": int(count),
        "release_date": album.release_date.isoformat() if album.release_date else None,
    }


def artist_doc(db: Session, artist_id: int) -> dict | None:
    artist = db.get(Artist, artist_id)
    if not artist or artist.status != "approved":
        return None
    return {"name": artist.name, "bio": artist.bio}


DOC_BUILDERS = {"track": ("tracks", track_doc), "album": ("albums", album_doc), "artist": ("artists", artist_doc)}


def bulk_actions_for(db: Session, entity: str, entity_id: int, action: str, index: str | None = None) -> list[dict]:
    """Opérations _bulk pour un événement de l'outbox (index ou suppression)."""
    alias, builder = DOC_BUILDERS[entity]
    target = index or alias
    doc = builder(db, entity_id) if action == "upsert" else None
    if doc is None:
        return [{"delete": {"_index": target, "_id": str(entity_id)}}]
    return [{"index": {"_index": target, "_id": str(entity_id)}}, doc]


def bulk(es: Elasticsearch, operations: list[dict]) -> None:
    if not operations:
        return
    result = es.bulk(operations=operations, refresh=False)
    if result.get("errors"):
        # Une suppression d'un document absent (404) n'est pas une erreur
        real = [
            item for item in result["items"]
            for op, detail in item.items()
            if detail.get("error") and not (op == "delete" and detail.get("status") == 404)
        ]
        if real:
            raise RuntimeError(f"Erreur d'indexation Elasticsearch : {real[:3]}")


# ---------- Recherche ----------

def _query(alias: str, q: str, size: int) -> dict:
    match = {"multi_match": {"query": q, "type": "bool_prefix", "fields": QUERY_FIELDS[alias], "fuzziness": "AUTO"}}
    if alias == "tracks":
        # Les titres populaires remontent
        match = {
            "function_score": {
                "query": match,
                "field_value_factor": {"field": "play_count", "modifier": "log2p", "missing": 0},
                "boost_mode": "multiply",
            }
        }
    return {"size": size, "query": match}


def msearch(es: Elasticsearch, q: str, size: int) -> dict[str, list[dict]]:
    """Interroge les trois index en une seule requête (_msearch)."""
    searches = []
    for alias in ALIASES:
        searches.append({"index": alias})
        searches.append(_query(alias, q, size))
    responses = es.msearch(searches=searches)["responses"]
    out = {}
    for alias, resp in zip(ALIASES, responses):
        hits = resp.get("hits", {}).get("hits", []) if "error" not in resp else []
        out[alias] = [{"id": int(h["_id"]), **h["_source"]} for h in hits]
    return out


def delete_doc(es: Elasticsearch, alias: str, doc_id: int) -> None:
    try:
        es.delete(index=alias, id=str(doc_id))
    except NotFoundError:
        pass
