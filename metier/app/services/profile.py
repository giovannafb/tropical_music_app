"""Profil de l'utilisateur connecté."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Artist, User
from app.schemas import ArtistProfile, MeOut


def me_out(user: User, artist: Artist | None) -> MeOut:
    return MeOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        artist=ArtistProfile(id=artist.id, name=artist.name, bio=artist.bio, status=artist.status) if artist else None,
    )


def load_me(db: Session, user_id: int) -> MeOut:
    user = db.get(User, user_id)
    artist = db.scalar(select(Artist).where(Artist.user_id == user_id)) if user.role == "artist" else None
    return me_out(user, artist)
