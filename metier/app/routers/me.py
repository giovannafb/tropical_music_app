from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.deps import CurrentUser, Db, Redis, require_role
from app.models import Artist
from app.repositories import catalog
from app.schemas import AlbumOut, BioIn, MeOut, PasswordChangeIn, PlaylistOut, TrackOut, UsernameIn
from app.services import albums, auth, playlists, sessions
from app.services.profile import load_me

router = APIRouter(prefix="/me", tags=["me"])

AnyRole = Annotated[CurrentUser, Depends(require_role("user", "artist", "admin"))]
UserRole = Annotated[CurrentUser, Depends(require_role("user"))]
ArtistRole = Annotated[CurrentUser, Depends(require_role("artist"))]


@router.get("")
def get_me(user: AnyRole, db: Db) -> MeOut:
    return load_me(db, user.id)


@router.patch("")
def change_username(body: UsernameIn, user: AnyRole, db: Db) -> MeOut:
    auth.change_username(db, user.id, body.username)
    return load_me(db, user.id)


@router.post("/password", status_code=204)
def change_password(body: PasswordChangeIn, user: AnyRole, response: Response, db: Db, r: Redis) -> None:
    auth.change_password(db, r, user.id, body.old_password, body.new_password)
    # Toutes les sessions sont fermées ; on en rouvre une pour l'appareil courant
    sessions.open_session(r, response, user.id, user.role, user.artist_id)


@router.patch("/artist")
def change_bio(body: BioIn, user: ArtistRole, db: Db) -> MeOut:
    artist = db.get(Artist, user.artist_id)
    albums.update_bio(db, artist, body.bio)
    return load_me(db, user.id)


@router.get("/likes/tracks")
def liked_tracks(user: UserRole, db: Db) -> list[TrackOut]:
    return catalog.liked_tracks(db, user.id)


@router.get("/likes/albums")
def liked_albums(user: UserRole, db: Db) -> list[AlbumOut]:
    return catalog.liked_albums(db, user.id)


@router.get("/playlists")
def my_playlists(user: UserRole, db: Db) -> list[PlaylistOut]:
    return playlists.list_for_user(db, user.id)
