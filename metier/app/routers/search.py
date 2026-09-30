from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, Db, Es, Redis, require_role
from app.core.storage import cover_urls
from app.repositories import catalog
from app.schemas import AlbumOut, AlbumRef, ArtistRef, SearchOut, TrackOut
from app.services import cache

router = APIRouter(tags=["search"])

# L'admin utilise aussi la recherche pour remplir la playlist à la une
SearchRole = Annotated[CurrentUser, Depends(require_role("user", "admin"))]


@router.get("/search")
def search(user: SearchRole, db: Db, r: Redis, es: Es, q: str = Query("", max_length=100)) -> SearchOut:
    """Résultats groupés Songs / Album / Artists (Elasticsearch, _msearch)."""
    q = q.strip()
    if not q:
        return SearchOut()
    raw = cache.search_results(es, r, q)
    tracks = [
        TrackOut(
            id=d["id"], title=d["title"], duration_s=d["duration_s"],
            artist=ArtistRef(id=d["artist_id"], name=d["artist_name"]),
            album=AlbumRef(id=d["album_id"], title=d["album_title"], **cover_urls(d.get("cover_path"))),
        )
        for d in raw["tracks"]
    ]
    liked_albums = catalog.liked_album_ids(db, user.id, (d["id"] for d in raw["albums"]))
    albums = [
        AlbumOut(
            id=d["id"], title=d["title"], artist=ArtistRef(id=d["artist_id"], name=d["artist_name"]),
            track_count=d.get("track_count", 0), duration_s=d.get("duration_s", 0),
            release_date=d.get("release_date"), liked=d["id"] in liked_albums,
            **cover_urls(d.get("cover_path")),
        )
        for d in raw["albums"]
    ]
    artists = [ArtistRef(id=d["id"], name=d["name"]) for d in raw["artists"]]
    return SearchOut(tracks=catalog.mark_liked_tracks(db, user.id, tracks), albums=albums, artists=artists)
