"""Espace artiste : uniquement sa propre musique (filtre par artist_id du compte connecté)."""
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select

from app.core.deps import CurrentUser, Db, Redis, clean_text, require_artist
from app.models import Album, Artist, Track
from app.repositories import catalog
from app.schemas import AlbumDetail, AlbumOut, RenameTrackIn, TrackDetail, TrackOut
from app.services import albums

router = APIRouter(prefix="/artist", tags=["artist"])

ArtistUser = Annotated[CurrentUser, Depends(require_artist)]


def _album_detail(db, album: Album, artist: Artist) -> AlbumDetail:
    base = catalog.albums_out(db, [(album, artist)])[0]
    return AlbumDetail(
        **base.model_dump(),
        like_count=catalog.album_like_count(db, album.id),
        tracks=catalog.album_tracks(db, album, artist),
    )


@router.get("/me/tracks")
def my_tracks(user: ArtistUser, db: Db) -> list[TrackOut]:
    """Titres des albums publiés de l'artiste (le brouillon est dans « New album »)."""
    artist = db.get(Artist, user.artist_id)
    rows = db.execute(
        select(Track, Album)
        .join(Album, Track.album_id == Album.id)
        .where(Album.artist_id == artist.id, Album.status == "published")
        .order_by(Album.release_date.desc(), Album.id.desc(), Track.position)
    ).all()
    return [catalog.track_out(t, al, artist) for t, al in rows]


@router.get("/me/albums")
def my_albums(user: ArtistUser, db: Db) -> list[AlbumOut]:
    artist = db.get(Artist, user.artist_id)
    return catalog.visible_albums_of_artist(db, artist)


@router.get("/me/draft")
def my_draft(user: ArtistUser, db: Db) -> AlbumDetail | None:
    """Brouillon en cours, repris automatiquement par l'écran « New album »."""
    draft = albums.get_draft(db, user.artist_id)
    return _album_detail(db, draft, db.get(Artist, user.artist_id)) if draft else None


@router.get("/tracks/{track_id}")
def my_track(track_id: int, user: ArtistUser, db: Db) -> TrackDetail:
    track, album = albums.own_track(db, user.artist_id, track_id)
    return catalog.track_detail(db, track, album, db.get(Artist, user.artist_id))


@router.get("/albums/{album_id}")
def my_album(album_id: int, user: ArtistUser, db: Db) -> AlbumDetail:
    album = albums.own_album(db, user.artist_id, album_id)
    return _album_detail(db, album, db.get(Artist, user.artist_id))


@router.post("/albums", status_code=201)
def create_album(
    user: ArtistUser,
    db: Db,
    title: Annotated[str, Form()],
    cover: Annotated[UploadFile | None, File()] = None,
) -> AlbumDetail:
    """Crée l'album brouillon (titre + cover)."""
    album = albums.create_draft(db, user.artist_id, clean_text(title, "title", 200), cover)
    return _album_detail(db, album, db.get(Artist, user.artist_id))


@router.patch("/albums/{album_id}")
def update_album(
    album_id: int,
    user: ArtistUser,
    db: Db,
    title: Annotated[str | None, Form()] = None,
    cover: Annotated[UploadFile | None, File()] = None,
) -> AlbumDetail:
    album = albums.update_draft(db, user.artist_id, album_id, clean_text(title, "title", 200, required=False), cover)
    return _album_detail(db, album, db.get(Artist, user.artist_id))


@router.post("/albums/{album_id}/tracks", status_code=201)
def upload_track(
    album_id: int,
    user: ArtistUser,
    db: Db,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
) -> TrackOut:
    """Upload d'une piste (une piste par requête)."""
    track = albums.add_track(db, user.artist_id, album_id, file, clean_text(title, "title", 200, required=False))
    album = db.get(Album, album_id)
    return catalog.track_out(track, album, db.get(Artist, user.artist_id))


@router.patch("/tracks/{track_id}")
def rename_track(track_id: int, body: RenameTrackIn, user: ArtistUser, db: Db, r: Redis) -> TrackOut:
    track = albums.rename_track(db, r, user.artist_id, track_id, body.title)
    return catalog.track_out(track, db.get(Album, track.album_id), db.get(Artist, user.artist_id))


@router.delete("/tracks/{track_id}", status_code=204)
def delete_track(track_id: int, user: ArtistUser, db: Db, r: Redis) -> None:
    albums.delete_track(db, r, user.artist_id, track_id)


@router.post("/albums/{album_id}/publish")
def publish_album(album_id: int, user: ArtistUser, db: Db, r: Redis) -> AlbumDetail:
    """Bouton « Upload » : publication de l'album."""
    album = albums.publish(db, r, user.artist_id, album_id)
    return _album_detail(db, album, db.get(Artist, user.artist_id))


@router.delete("/albums/{album_id}", status_code=204)
def delete_album(album_id: int, user: ArtistUser, db: Db, r: Redis) -> None:
    albums.delete_album(db, r, user.artist_id, album_id)
