"""Espace admin : validation des artistes et playlist « à la une »."""
import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError, not_found
from app.models import FEATURED_PLAYLIST_KEY, AppSetting, Artist, Playlist, User
from app.repositories import outbox
from app.schemas import PendingArtistOut
from app.services import emails
from app.services.cache import featured_playlist_id, invalidate_home


def list_artists(db: Session, status: str) -> list[PendingArtistOut]:
    rows = db.execute(
        select(Artist, User).join(User, Artist.user_id == User.id).where(Artist.status == status).order_by(Artist.id)
    ).all()
    return [
        PendingArtistOut(
            id=a.id, name=a.name, bio=a.bio, status=a.status, username=u.username,
            email=u.email, rejection_reason=a.rejection_reason,
        )
        for a, u in rows
    ]


def _pending_artist(db: Session, artist_id: int) -> tuple[Artist, User]:
    artist = db.get(Artist, artist_id)
    if not artist:
        raise not_found("Artist")
    if artist.status != "pending":
        raise AppError(409, "ALREADY_REVIEWED", "This artist has already been reviewed")
    return artist, db.get(User, artist.user_id)


def approve(db: Session, r: redis.Redis, admin_id: int, artist_id: int) -> None:
    artist, user = _pending_artist(db, artist_id)
    artist.status = "approved"
    artist.reviewed_by = admin_id
    artist.reviewed_at = utcnow()
    artist.rejection_reason = None
    outbox.add(db, "artist", artist.id)
    db.commit()
    emails.send_artist_approved(r, user.email, artist.name)


def reject(db: Session, r: redis.Redis, admin_id: int, artist_id: int, reason: str) -> None:
    artist, user = _pending_artist(db, artist_id)
    artist.status = "rejected"
    artist.reviewed_by = admin_id
    artist.reviewed_at = utcnow()
    artist.rejection_reason = reason
    db.commit()
    emails.send_artist_rejected(r, user.email, artist.name, reason)


def set_featured(db: Session, r: redis.Redis, playlist_id: int) -> None:
    """Désigne la playlist à la une (elle doit appartenir à un compte admin)."""
    row = db.execute(select(Playlist, User).join(User, Playlist.user_id == User.id).where(Playlist.id == playlist_id)).first()
    if not row or row[1].role != "admin":
        raise not_found("Playlist")
    setting = db.get(AppSetting, FEATURED_PLAYLIST_KEY)
    if setting:
        setting.value = str(playlist_id)
    else:
        db.add(AppSetting(key=FEATURED_PLAYLIST_KEY, value=str(playlist_id)))
    db.commit()
    invalidate_home(r)


def featured_playlist(db: Session) -> Playlist:
    playlist_id = featured_playlist_id(db)
    playlist = db.get(Playlist, playlist_id) if playlist_id else None
    if not playlist:
        raise AppError(404, "NO_FEATURED_PLAYLIST", "No featured playlist (run create_admin.py)")
    return playlist
