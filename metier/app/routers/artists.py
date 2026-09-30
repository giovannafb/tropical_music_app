"""Pop-up artiste côté User (nom, bio, albums)."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, Db, require_role
from app.core.errors import not_found
from app.models import Artist
from app.repositories import catalog
from app.schemas import ArtistOut

router = APIRouter(prefix="/artists", tags=["artists"])

UserRole = Annotated[CurrentUser, Depends(require_role("user"))]


@router.get("/{artist_id}")
def artist_detail(artist_id: int, user: UserRole, db: Db) -> ArtistOut:
    artist = db.get(Artist, artist_id)
    if not artist or artist.status != "approved":
        raise not_found("Artist")
    return ArtistOut(
        id=artist.id, name=artist.name, bio=artist.bio,
        albums=catalog.visible_albums_of_artist(db, artist, user.id),
    )
