"""Requêtes MySQL du catalogue (titres, albums, artistes, likes)."""
from collections.abc import Iterable

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.storage import cover_urls
from app.models import Album, AlbumLike, Artist, Track, TrackLike
from app.schemas import AlbumOut, AlbumRef, ArtistRef, TrackDetail, TrackOut

# Un user ne voit que les albums publiés d'artistes validés
VISIBLE = and_(Album.status == "published", Artist.status == "approved")


def _track_select():
    return (
        select(Track, Album, Artist)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Album.artist_id == Artist.id)
    )


def track_out(track: Track, album: Album, artist: Artist, liked: bool = False) -> TrackOut:
    return TrackOut(
        id=track.id,
        title=track.title,
        duration_s=track.duration_s,
        artist=ArtistRef(id=artist.id, name=artist.name),
        album=AlbumRef(id=album.id, title=album.title, **cover_urls(album.cover_path)),
        liked=liked,
    )


def liked_track_ids(db: Session, user_id: int, ids: Iterable[int]) -> set[int]:
    ids = list(set(ids))
    if not ids:
        return set()
    rows = db.scalars(select(TrackLike.track_id).where(TrackLike.user_id == user_id, TrackLike.track_id.in_(ids)))
    return set(rows)


def liked_album_ids(db: Session, user_id: int, ids: Iterable[int]) -> set[int]:
    ids = list(set(ids))
    if not ids:
        return set()
    rows = db.scalars(select(AlbumLike.album_id).where(AlbumLike.user_id == user_id, AlbumLike.album_id.in_(ids)))
    return set(rows)


def get_visible_track(db: Session, track_id: int):
    return db.execute(_track_select().where(Track.id == track_id, VISIBLE)).first()


def get_track_any(db: Session, track_id: int):
    return db.execute(_track_select().where(Track.id == track_id)).first()


def visible_tracks_by_ids(db: Session, ids: list[int]) -> list[TrackOut]:
    """Titres visibles, dans l'ordre des ids demandés."""
    if not ids:
        return []
    rows = db.execute(_track_select().where(Track.id.in_(ids), VISIBLE)).all()
    by_id = {t.id: track_out(t, al, ar) for t, al, ar in rows}
    return [by_id[i] for i in ids if i in by_id]


def mark_liked_tracks(db: Session, user_id: int, tracks: list[TrackOut]) -> list[TrackOut]:
    liked = liked_track_ids(db, user_id, (t.id for t in tracks))
    return [t.model_copy(update={"liked": t.id in liked}) for t in tracks]


def track_detail(db: Session, track: Track, album: Album, artist: Artist, liked: bool = False) -> TrackDetail:
    like_count = db.scalar(select(func.count()).select_from(TrackLike).where(TrackLike.track_id == track.id))
    return TrackDetail(
        **track_out(track, album, artist, liked).model_dump(),
        release_date=album.release_date,
        play_count=track.play_count,
        like_count=like_count or 0,
    )


def liked_tracks(db: Session, user_id: int) -> list[TrackOut]:
    rows = db.execute(
        _track_select()
        .join(TrackLike, and_(TrackLike.track_id == Track.id, TrackLike.user_id == user_id))
        .where(VISIBLE)
        .order_by(TrackLike.created_at.desc(), Track.id.desc())
    ).all()
    return [track_out(t, al, ar, liked=True) for t, al, ar in rows]


def album_stats(db: Session, album_ids: Iterable[int]) -> dict[int, tuple[int, int]]:
    """album_id -> (nombre de titres, durée totale en s)."""
    ids = list(set(album_ids))
    if not ids:
        return {}
    rows = db.execute(
        select(Track.album_id, func.count(Track.id), func.coalesce(func.sum(Track.duration_s), 0))
        .where(Track.album_id.in_(ids))
        .group_by(Track.album_id)
    ).all()
    return {album_id: (int(count), int(total)) for album_id, count, total in rows}


def album_out(album: Album, artist: Artist, stats: dict, liked: bool = False) -> AlbumOut:
    count, total = stats.get(album.id, (0, 0))
    return AlbumOut(
        id=album.id,
        title=album.title,
        artist=ArtistRef(id=artist.id, name=artist.name),
        track_count=count,
        duration_s=total,
        release_date=album.release_date,
        status=album.status,
        liked=liked,
        **cover_urls(album.cover_path),
    )


def albums_out(db: Session, rows: list[tuple[Album, Artist]], user_id: int | None = None) -> list[AlbumOut]:
    stats = album_stats(db, (al.id for al, _ in rows))
    liked = liked_album_ids(db, user_id, (al.id for al, _ in rows)) if user_id else set()
    return [album_out(al, ar, stats, al.id in liked) for al, ar in rows]


def get_visible_album(db: Session, album_id: int):
    return db.execute(
        select(Album, Artist).join(Artist, Album.artist_id == Artist.id).where(Album.id == album_id, VISIBLE)
    ).first()


def album_tracks(db: Session, album: Album, artist: Artist, user_id: int | None = None) -> list[TrackOut]:
    tracks = db.scalars(select(Track).where(Track.album_id == album.id).order_by(Track.position, Track.id)).all()
    liked = liked_track_ids(db, user_id, (t.id for t in tracks)) if user_id else set()
    return [track_out(t, album, artist, t.id in liked) for t in tracks]


def album_like_count(db: Session, album_id: int) -> int:
    return db.scalar(select(func.count()).select_from(AlbumLike).where(AlbumLike.album_id == album_id)) or 0


def liked_albums(db: Session, user_id: int) -> list[AlbumOut]:
    rows = db.execute(
        select(Album, Artist)
        .join(Artist, Album.artist_id == Artist.id)
        .join(AlbumLike, and_(AlbumLike.album_id == Album.id, AlbumLike.user_id == user_id))
        .where(VISIBLE)
        .order_by(AlbumLike.created_at.desc(), Album.id.desc())
    ).all()
    return albums_out(db, [tuple(r) for r in rows], user_id)


def visible_albums_of_artist(db: Session, artist: Artist, user_id: int | None = None) -> list[AlbumOut]:
    albums = db.scalars(
        select(Album)
        .where(Album.artist_id == artist.id, Album.status == "published")
        .order_by(Album.release_date.desc(), Album.id.desc())
    ).all()
    return albums_out(db, [(al, artist) for al in albums], user_id)
