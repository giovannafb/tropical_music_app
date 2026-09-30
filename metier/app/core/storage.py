"""Stockage des fichiers sur le volume /data : audio (MP3) et covers.

- Les fichiers audio ne sont jamais en base : seul leur nom est stocké.
- Noms générés (UUID), jamais le nom envoyé par l'utilisateur.
- Type réel vérifié (mutagen pour l'audio, Pillow pour les images).
"""
import os
import uuid
from dataclasses import dataclass
from typing import BinaryIO

from mutagen import MutagenError
from mutagen.mp3 import MP3, HeaderNotFoundError
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.core.errors import AppError

COVER_SIZES = (600, 128)
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
CHUNK = 1024 * 1024


def audio_dir() -> str:
    return os.path.join(get_settings().media_root, "audio")


def covers_dir() -> str:
    return os.path.join(get_settings().media_root, "covers")


def cover_urls(cover: str | None) -> dict:
    """URLs publiques servies par Nginx (/covers/)."""
    if not cover:
        return {"cover_url": None, "cover_small_url": None}
    return {"cover_url": f"/covers/{cover}_600.jpg", "cover_small_url": f"/covers/{cover}_128.jpg"}


def _copy_limited(src: BinaryIO, dst_path: str, limit: int) -> None:
    written = 0
    with open(dst_path, "wb") as dst:
        while chunk := src.read(CHUNK):
            written += len(chunk)
            if written > limit:
                raise AppError(413, "FILE_TOO_LARGE", f"File too large (max {limit // (1024 * 1024)} MB)")
            dst.write(chunk)


@dataclass
class StoredAudio:
    file_path: str
    duration_s: int


def save_audio(src: BinaryIO) -> StoredAudio:
    os.makedirs(audio_dir(), exist_ok=True)
    name = f"{uuid.uuid4().hex}.mp3"
    path = os.path.join(audio_dir(), name)
    try:
        _copy_limited(src, path, get_settings().max_audio_bytes)
        try:
            info = MP3(path).info
        except (MutagenError, HeaderNotFoundError, OSError, ValueError):
            raise AppError(400, "INVALID_AUDIO", "Only MP3 files are accepted")
        if not info.length or info.length <= 0:
            raise AppError(400, "INVALID_AUDIO", "Only MP3 files are accepted")
    except Exception:
        _remove(path)
        raise
    return StoredAudio(file_path=name, duration_s=max(1, round(info.length)))


def save_cover(src: BinaryIO) -> str:
    """Enregistre la cover en 600×600 et 128×128 (JPEG) ; renvoie son identifiant."""
    os.makedirs(covers_dir(), exist_ok=True)
    cover_id = uuid.uuid4().hex
    tmp = os.path.join(covers_dir(), f"{cover_id}.upload")
    try:
        _copy_limited(src, tmp, get_settings().max_cover_bytes)
        try:
            with Image.open(tmp) as probe:
                fmt = probe.format
                probe.verify()
            if fmt not in ALLOWED_IMAGE_FORMATS:
                raise AppError(400, "INVALID_IMAGE", "Cover must be a JPEG, PNG or WebP image")
            with Image.open(tmp) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                for size in COVER_SIZES:
                    ImageOps.fit(img, (size, size), Image.Resampling.LANCZOS).save(
                        os.path.join(covers_dir(), f"{cover_id}_{size}.jpg"), "JPEG", quality=85
                    )
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
            raise AppError(400, "INVALID_IMAGE", "Cover must be a JPEG, PNG or WebP image")
    except Exception:
        delete_cover(cover_id)
        raise
    finally:
        _remove(tmp)
    return cover_id


def delete_audio(file_path: str | None) -> None:
    if file_path:
        _remove(os.path.join(audio_dir(), os.path.basename(file_path)))


def delete_cover(cover_id: str | None) -> None:
    if cover_id:
        for size in COVER_SIZES:
            _remove(os.path.join(covers_dir(), f"{os.path.basename(cover_id)}_{size}.jpg"))


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
