"""Espace artiste : brouillon d'album, upload des pistes, publication, suppression.

Un artiste n'agit que sur ses propres contenus (filtre par artist_id du compte connecté).
Un seul brouillon par artiste, repris par l'écran « New album ».
"""
import os
from datetime import date

import redis
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.errors import AppError, not_found
from app.models import Album, Artist, Track
from app.repositories import outbox
from app.services.cache import invalidate_home


def get_draft(db: Session, artist_id: int) -> Album | None:
    return db.scalar(select(Album).where(Album.artist_id == artist_id, Album.status == "draft").order_by(Album.id))


def own_album(db: Session, artist_id: int, album_id: int) -> Album:
    album = db.get(Album, album_id)
    if not album or album.artist_id != artist_id:
        raise not_found("Album")
    return album


def own_draft(db: Session, artist_id: int, album_id: int) -> Album:
    album = own_album(db, artist_id, album_id)
    if album.status != "draft":
        raise AppError(409, "ALBUM_PUBLISHED", "This album is already published")
    return album


def own_track(db: Session, artist_id: int, track_id: int) -> tuple[Track, Album]:
    row = db.execute(select(Track, Album).join(Album, Track.album_id == Album.id).where(Track.id == track_id)).first()
    if not row or row[1].artist_id != artist_id:
        raise not_found("Track")
    return row[0], row[1]


def _replace_cover(album: Album, cover: UploadFile | None) -> str | None:
    """Enregistre la nouvelle cover ; renvoie l'ancienne (à supprimer après commit)."""
    if cover is None or not cover.filename:
        return None
    old = album.cover_path
    album.cover_path = storage.save_cover(cover.file)
    return old


def create_draft(db: Session, artist_id: int, title: str, cover: UploadFile | None) -> Album:
    if get_draft(db, artist_id):
        raise AppError(409, "DRAFT_EXISTS", "You already have an album in progress")
    album = Album(artist_id=artist_id, title=title, status="draft")
    _replace_cover(album, cover)
    db.add(album)
    db.commit()
    return album


def update_draft(db: Session, artist_id: int, album_id: int, title: str | None, cover: UploadFile | None) -> Album:
    album = own_draft(db, artist_id, album_id)
    if title is not None:
        album.title = title
    old_cover = _replace_cover(album, cover)
    db.commit()
    storage.delete_cover(old_cover)
    return album


def add_track(db: Session, artist_id: int, album_id: int, upload: UploadFile, title: str | None) -> Track:
    album = own_draft(db, artist_id, album_id)
    stored = storage.save_audio(upload.file)
    if not title:
        title = os.path.splitext(os.path.basename(upload.filename or ""))[0].strip() or "Untitled"
    position = (db.scalar(select(func.max(Track.position)).where(Track.album_id == album.id)) or 0) + 1
    track = Track(
        album_id=album.id, title=title[:200], position=position,
        duration_s=stored.duration_s, file_path=stored.file_path, play_count=0,
    )
    db.add(track)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete_audio(stored.file_path)
        raise
    return track


def rename_track(db: Session, r: redis.Redis, artist_id: int, track_id: int, title: str) -> Track:
    track, album = own_track(db, artist_id, track_id)
    track.title = title
    if album.status == "published":
        outbox.add(db, "track", track.id)
    db.commit()
    if album.status == "published":
        invalidate_home(r)
    return track


def delete_track(db: Session, r: redis.Redis, artist_id: int, track_id: int) -> None:
    track, album = own_track(db, artist_id, track_id)
    file_path = track.file_path
    db.delete(track)
    if album.status == "published":
        outbox.add(db, "track", track_id, "delete")
        outbox.add(db, "album", album.id)       # nombre de titres et durée changent
    db.commit()
    storage.delete_audio(file_path)
    if album.status == "published":
        invalidate_home(r)


def publish(db: Session, r: redis.Redis, artist_id: int, album_id: int) -> Album:
    """Bouton « Upload » : publication, date de sortie = aujourd'hui, indexation ES."""
    album = own_draft(db, artist_id, album_id)
    if not album.cover_path:
        raise AppError(400, "COVER_REQUIRED", "Add an album cover before uploading")
    track_ids = list(db.scalars(select(Track.id).where(Track.album_id == album.id)))
    if not track_ids:
        raise AppError(400, "NO_TRACKS", "Add at least one track before uploading")
    album.status = "published"
    album.release_date = date.today()
    outbox.add(db, "album", album.id)
    outbox.add_many(db, "track", track_ids)
    outbox.add(db, "artist", artist_id)
    db.commit()
    invalidate_home(r)
    return album


def delete_album(db: Session, r: redis.Redis, artist_id: int, album_id: int) -> None:
    album = own_album(db, artist_id, album_id)
    tracks = list(db.scalars(select(Track).where(Track.album_id == album.id)))
    files = [t.file_path for t in tracks]
    cover = album.cover_path
    was_published = album.status == "published"
    if was_published:
        outbox.add(db, "album", album.id, "delete")
        outbox.add_many(db, "track", [t.id for t in tracks], "delete")
    db.delete(album)   # les pistes, likes et entrées de playlists suivent (ON DELETE CASCADE)
    db.commit()
    for f in files:
        storage.delete_audio(f)
    storage.delete_cover(cover)
    if was_published:
        invalidate_home(r)


def update_bio(db: Session, artist: Artist, bio: str) -> Artist:
    artist.bio = bio
    outbox.add(db, "artist", artist.id)
    db.commit()
    return artist
