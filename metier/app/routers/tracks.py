from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentUser, Db, Redis, require_role
from app.core.errors import not_found
from app.models import TrackLike
from app.repositories import catalog
from app.schemas import TrackDetail, TrackOut
from app.services import cache, counters

router = APIRouter(tags=["tracks"])

UserRole = Annotated[CurrentUser, Depends(require_role("user"))]


@router.get("/home")
def home(user: UserRole, db: Db, r: Redis) -> list[TrackOut]:
    """Titres « à la une » : contenu de la playlist gérée par l'admin (en cache)."""
    return catalog.mark_liked_tracks(db, user.id, cache.featured_tracks(db, r))


def _visible_track(db, track_id: int):
    row = catalog.get_visible_track(db, track_id)
    if not row:
        raise not_found("Track")
    return row


@router.get("/tracks/{track_id}")
def track_detail(track_id: int, user: UserRole, db: Db) -> TrackDetail:
    track, album, artist = _visible_track(db, track_id)
    liked = track.id in catalog.liked_track_ids(db, user.id, [track.id])
    return catalog.track_detail(db, track, album, artist, liked)


@router.put("/tracks/{track_id}/like", status_code=204)
def like_track(track_id: int, user: UserRole, db: Db) -> None:
    _visible_track(db, track_id)
    if not db.get(TrackLike, (user.id, track_id)):
        db.add(TrackLike(user_id=user.id, track_id=track_id))
        try:
            db.commit()
        except IntegrityError:   # double clic : déjà liké
            db.rollback()


@router.delete("/tracks/{track_id}/like", status_code=204)
def unlike_track(track_id: int, user: UserRole, db: Db) -> None:
    like = db.get(TrackLike, (user.id, track_id))
    if like:
        db.delete(like)
        db.commit()


@router.post("/tracks/{track_id}/play", status_code=204)
def play(track_id: int, user: UserRole, db: Db, r: Redis) -> None:
    """Appelé par le client après 30 s d'écoute, une fois par lecture."""
    _visible_track(db, track_id)
    counters.record_play(r, user.id, track_id)
