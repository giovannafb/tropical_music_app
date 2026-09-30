"""Playlists : un user ne modifie que ses propres playlists.
La playlist « à la une » appartient au compte admin et est gérée depuis l'espace admin."""
import redis
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.errors import AppError, not_found
from app.models import Playlist, PlaylistTrack, Track
from app.repositories import catalog
from app.schemas import PlaylistDetail, PlaylistOut
from app.services.cache import featured_playlist_id, invalidate_home


def own_playlist(db: Session, user_id: int, playlist_id: int) -> Playlist:
    playlist = db.get(Playlist, playlist_id)
    if not playlist or playlist.user_id != user_id:
        raise not_found("Playlist")
    return playlist


def _stats(db: Session, ids: list[int]) -> dict[int, tuple[int, int]]:
    """Nombre de titres (COUNT) et durée totale (SUM duration_s)."""
    if not ids:
        return {}
    rows = db.execute(
        select(PlaylistTrack.playlist_id, func.count(), func.coalesce(func.sum(Track.duration_s), 0))
        .join(Track, Track.id == PlaylistTrack.track_id)
        .where(PlaylistTrack.playlist_id.in_(ids))
        .group_by(PlaylistTrack.playlist_id)
    ).all()
    return {pid: (int(c), int(d)) for pid, c, d in rows}


def playlist_out(p: Playlist, stats: dict) -> PlaylistOut:
    count, total = stats.get(p.id, (0, 0))
    return PlaylistOut(id=p.id, name=p.name, track_count=count, duration_s=total, **storage.cover_urls(p.cover_path))


def summary(db: Session, playlist: Playlist) -> PlaylistOut:
    return playlist_out(playlist, _stats(db, [playlist.id]))


def list_for_user(db: Session, user_id: int) -> list[PlaylistOut]:
    playlists = list(db.scalars(select(Playlist).where(Playlist.user_id == user_id).order_by(Playlist.id)))
    stats = _stats(db, [p.id for p in playlists])
    return [playlist_out(p, stats) for p in playlists]


def detail(db: Session, playlist: Playlist, user_id: int) -> PlaylistDetail:
    ids = list(db.scalars(
        select(PlaylistTrack.track_id).where(PlaylistTrack.playlist_id == playlist.id).order_by(PlaylistTrack.position)
    ))
    tracks = catalog.mark_liked_tracks(db, user_id, catalog.visible_tracks_by_ids(db, ids))
    return PlaylistDetail(**summary(db, playlist).model_dump(), tracks=tracks)


def _next_position(db: Session, playlist_id: int) -> int:
    return (db.scalar(select(func.max(PlaylistTrack.position)).where(PlaylistTrack.playlist_id == playlist_id)) or 0) + 1


def _append(db: Session, playlist: Playlist, track_id: int) -> bool:
    """Ajoute un titre visible ; ne fait rien s'il est déjà présent."""
    if not catalog.get_visible_track(db, track_id):
        raise not_found("Track")
    if db.get(PlaylistTrack, (playlist.id, track_id)):
        return False
    db.add(PlaylistTrack(playlist_id=playlist.id, track_id=track_id, position=_next_position(db, playlist.id)))
    db.flush()
    return True


def create(db: Session, user_id: int, name: str, cover: UploadFile | None, track_ids: list[int]) -> Playlist:
    playlist = Playlist(user_id=user_id, name=name)
    if cover is not None and cover.filename:
        playlist.cover_path = storage.save_cover(cover.file)
    db.add(playlist)
    try:
        db.flush()
        for track_id in dict.fromkeys(track_ids):
            _append(db, playlist, track_id)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete_cover(playlist.cover_path)
        raise
    return playlist


def update(db: Session, playlist: Playlist, name: str | None, cover: UploadFile | None) -> Playlist:
    old_cover = None
    if name is not None:
        playlist.name = name
    if cover is not None and cover.filename:
        old_cover = playlist.cover_path
        playlist.cover_path = storage.save_cover(cover.file)
    db.commit()
    storage.delete_cover(old_cover)
    return playlist


def delete(db: Session, playlist: Playlist) -> None:
    if featured_playlist_id(db) == playlist.id:
        raise AppError(409, "FEATURED_PLAYLIST", "The featured playlist cannot be deleted")
    cover = playlist.cover_path
    db.delete(playlist)
    db.commit()
    storage.delete_cover(cover)


def add_track(db: Session, r: redis.Redis, playlist: Playlist, track_id: int) -> None:
    _append(db, playlist, track_id)
    db.commit()
    if featured_playlist_id(db) == playlist.id:
        invalidate_home(r)


def remove_track(db: Session, r: redis.Redis, playlist: Playlist, track_id: int) -> None:
    link = db.get(PlaylistTrack, (playlist.id, track_id))
    if link:
        db.delete(link)
        db.commit()
    if featured_playlist_id(db) == playlist.id:
        invalidate_home(r)
