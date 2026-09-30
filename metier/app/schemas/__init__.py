"""Schémas Pydantic (entrées / sorties de l'API)."""
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator

PASSWORD_MIN = 8


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _check_username(value):
    """Pas de « @ » : la connexion accepte username OU email."""
    value = _strip(value)
    if isinstance(value, str) and "@" in value:
        raise ValueError("Username cannot contain '@'")
    return value


# ---------- Entrées ----------

class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=PASSWORD_MIN, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def check_username(cls, v):
        return _check_username(v)


class RegisterArtistIn(RegisterIn):
    artist_name: str = Field(min_length=1, max_length=100)
    bio: str = Field(min_length=1, max_length=5000)

    @field_validator("artist_name", "bio", mode="before")
    @classmethod
    def strip_text(cls, v):
        return _strip(v)


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=255, description="Username ou email")
    password: str = Field(min_length=1, max_length=128)


class EmailIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=PASSWORD_MIN, max_length=128)


class UsernameIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)

    @field_validator("username", mode="before")
    @classmethod
    def check_username(cls, v):
        return _check_username(v)


class PasswordChangeIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=128)


class BioIn(BaseModel):
    bio: str = Field(min_length=1, max_length=5000)

    @field_validator("bio", mode="before")
    @classmethod
    def strip_bio(cls, v):
        return _strip(v)


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, v):
        return _strip(v)


class FeaturedPlaylistIn(BaseModel):
    playlist_id: int


class TrackIdIn(BaseModel):
    track_id: int


class RenameTrackIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v):
        return _strip(v)


# ---------- Sorties ----------

class ArtistRef(BaseModel):
    id: int
    name: str


class AlbumRef(BaseModel):
    id: int
    title: str
    cover_url: str | None = None
    cover_small_url: str | None = None


class TrackOut(BaseModel):
    id: int
    title: str
    duration_s: int
    artist: ArtistRef
    album: AlbumRef
    liked: bool = False


class TrackDetail(TrackOut):
    release_date: date | None = None
    play_count: int = 0
    like_count: int = 0


class AlbumOut(BaseModel):
    id: int
    title: str
    artist: ArtistRef
    cover_url: str | None = None
    cover_small_url: str | None = None
    track_count: int = 0
    duration_s: int = 0
    release_date: date | None = None
    status: str = "published"
    liked: bool = False


class AlbumDetail(AlbumOut):
    like_count: int = 0
    tracks: list[TrackOut] = []


class ArtistOut(BaseModel):
    id: int
    name: str
    bio: str
    albums: list[AlbumOut] = []


class SearchOut(BaseModel):
    tracks: list[TrackOut] = []
    albums: list[AlbumOut] = []
    artists: list[ArtistRef] = []


class PlaylistOut(BaseModel):
    id: int
    name: str
    cover_url: str | None = None
    cover_small_url: str | None = None
    track_count: int = 0
    duration_s: int = 0


class PlaylistDetail(PlaylistOut):
    tracks: list[TrackOut] = []


class ArtistProfile(BaseModel):
    id: int
    name: str
    bio: str
    status: str


class MeOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    artist: ArtistProfile | None = None


class PendingArtistOut(BaseModel):
    id: int
    name: str
    bio: str
    status: str
    username: str
    email: str
    rejection_reason: str | None = None
