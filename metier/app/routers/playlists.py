from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.deps import CurrentUser, Db, Redis, clean_text, require_role
from app.schemas import PlaylistDetail, PlaylistOut, TrackIdIn
from app.services import playlists

router = APIRouter(prefix="/playlists", tags=["playlists"])

UserRole = Annotated[CurrentUser, Depends(require_role("user"))]


@router.post("", status_code=201)
def create_playlist(
    user: UserRole,
    db: Db,
    name: Annotated[str, Form()],
    cover: Annotated[UploadFile | None, File()] = None,
    track_ids: Annotated[list[int], Form()] = [],
) -> PlaylistOut:
    """Multipart : nom + cover (optionnelle) + titres."""
    playlist = playlists.create(db, user.id, clean_text(name, "name", 100), cover, track_ids)
    return playlists.summary(db, playlist)


@router.get("/{playlist_id}")
def get_playlist(playlist_id: int, user: UserRole, db: Db) -> PlaylistDetail:
    return playlists.detail(db, playlists.own_playlist(db, user.id, playlist_id), user.id)


@router.patch("/{playlist_id}")
def update_playlist(
    playlist_id: int,
    user: UserRole,
    db: Db,
    name: Annotated[str | None, Form()] = None,
    cover: Annotated[UploadFile | None, File()] = None,
) -> PlaylistOut:
    playlist = playlists.own_playlist(db, user.id, playlist_id)
    playlists.update(db, playlist, clean_text(name, "name", 100, required=False), cover)
    return playlists.summary(db, playlist)


@router.delete("/{playlist_id}", status_code=204)
def delete_playlist(playlist_id: int, user: UserRole, db: Db) -> None:
    playlists.delete(db, playlists.own_playlist(db, user.id, playlist_id))


@router.post("/{playlist_id}/tracks", status_code=204)
def add_track(playlist_id: int, body: TrackIdIn, user: UserRole, db: Db, r: Redis) -> None:
    playlists.add_track(db, r, playlists.own_playlist(db, user.id, playlist_id), body.track_id)


@router.delete("/{playlist_id}/tracks/{track_id}", status_code=204)
def remove_track(playlist_id: int, track_id: int, user: UserRole, db: Db, r: Redis) -> None:
    playlists.remove_track(db, r, playlists.own_playlist(db, user.id, playlist_id), track_id)
