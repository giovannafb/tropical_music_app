from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, Db, Redis, require_role
from app.schemas import FeaturedPlaylistIn, PendingArtistOut, PlaylistDetail, RejectIn, TrackIdIn
from app.services import admin, playlists

router = APIRouter(prefix="/admin", tags=["admin"])

AdminRole = Annotated[CurrentUser, Depends(require_role("admin"))]


@router.get("/artists")
def list_artists(
    user: AdminRole, db: Db, status: Literal["pending", "approved", "rejected"] = "pending"
) -> list[PendingArtistOut]:
    return admin.list_artists(db, status)


@router.post("/artists/{artist_id}/approve", status_code=204)
def approve(artist_id: int, user: AdminRole, db: Db, r: Redis) -> None:
    admin.approve(db, r, user.id, artist_id)


@router.post("/artists/{artist_id}/reject", status_code=204)
def reject(artist_id: int, body: RejectIn, user: AdminRole, db: Db, r: Redis) -> None:
    admin.reject(db, r, user.id, artist_id, body.reason)


@router.put("/featured-playlist", status_code=204)
def set_featured(body: FeaturedPlaylistIn, user: AdminRole, db: Db, r: Redis) -> None:
    """Désigne la playlist à la une."""
    admin.set_featured(db, r, body.playlist_id)


@router.get("/featured-playlist")
def get_featured(user: AdminRole, db: Db) -> PlaylistDetail:
    return playlists.detail(db, admin.featured_playlist(db), user.id)


@router.post("/featured-playlist/tracks", status_code=204)
def add_featured_track(body: TrackIdIn, user: AdminRole, db: Db, r: Redis) -> None:
    playlists.add_track(db, r, admin.featured_playlist(db), body.track_id)


@router.delete("/featured-playlist/tracks/{track_id}", status_code=204)
def remove_featured_track(track_id: int, user: AdminRole, db: Db, r: Redis) -> None:
    playlists.remove_track(db, r, admin.featured_playlist(db), track_id)
