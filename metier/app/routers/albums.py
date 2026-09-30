from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentUser, Db, require_role
from app.core.errors import not_found
from app.models import AlbumLike
from app.repositories import catalog
from app.schemas import AlbumDetail

router = APIRouter(prefix="/albums", tags=["albums"])

UserRole = Annotated[CurrentUser, Depends(require_role("user"))]


def _visible_album(db, album_id: int):
    row = catalog.get_visible_album(db, album_id)
    if not row:
        raise not_found("Album")
    return row


@router.get("/{album_id}")
def album_detail(album_id: int, user: UserRole, db: Db) -> AlbumDetail:
    """Pop-up album : infos, titres et bouton like."""
    album, artist = _visible_album(db, album_id)
    base = catalog.albums_out(db, [(album, artist)], user.id)[0]
    return AlbumDetail(
        **base.model_dump(),
        like_count=catalog.album_like_count(db, album.id),
        tracks=catalog.album_tracks(db, album, artist, user.id),
    )


@router.put("/{album_id}/like", status_code=204)
def like_album(album_id: int, user: UserRole, db: Db) -> None:
    _visible_album(db, album_id)
    if not db.get(AlbumLike, (user.id, album_id)):
        db.add(AlbumLike(user_id=user.id, album_id=album_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()


@router.delete("/{album_id}/like", status_code=204)
def unlike_album(album_id: int, user: UserRole, db: Db) -> None:
    like = db.get(AlbumLike, (user.id, album_id))
    if like:
        db.delete(like)
        db.commit()
