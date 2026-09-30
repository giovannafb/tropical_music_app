"""Importe le jeu de données FMA (fma_small) : comptes artistes déjà validés, albums publiés,
fichiers audio copiés sur le volume (/data/audio, noms UUID), puis indexation ES via l'outbox.

Les archives sont lues directement (pas besoin de les extraire) :
    python -m app.scripts.seed_fma --metadata /fma/fma_metadata.zip --audio /fma/fma_small.zip [--limit 200]

Le mot de passe commun des comptes artistes importés est lu dans SEED_ARTIST_PASSWORD.
Relancer le script reprend là où il s'était arrêté (artistes déjà importés ignorés).
"""
import argparse
import csv
import html
import io
import os
import re
import sys
import zipfile
from collections import OrderedDict
from datetime import date, datetime

from sqlalchemy import select

from app.core import storage
from app.core.db import get_sessionmaker
from app.core.errors import AppError
from app.core.security import hash_password
from app.models import Album, Artist, Track, User
from app.repositories import outbox

TAG_RE = re.compile(r"<[^>]+>")
SPACES_RE = re.compile(r"\s+")


def clean_html(text: str, limit: int) -> str:
    return SPACES_RE.sub(" ", html.unescape(TAG_RE.sub(" ", text or ""))).strip()[:limit]


def parse_date(*values: str) -> date:
    for value in values:
        if value:
            try:
                return datetime.fromisoformat(value.strip()).date()
            except ValueError:
                continue
    return date.today()


def read_small_tracks(metadata_zip: str) -> "OrderedDict[str, dict]":
    """Regroupe les titres du sous-ensemble « small » par artiste puis par album."""
    artists: OrderedDict[str, dict] = OrderedDict()
    with zipfile.ZipFile(metadata_zip) as z, z.open("fma_metadata/tracks.csv") as f:
        reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8"))
        top, sub = next(reader), next(reader)
        next(reader)
        cols = ["track_id" if not a else (f"{a}.{b}" if b else a) for a, b in zip(top, sub)]
        for row in reader:
            d = dict(zip(cols, row))
            if d.get("set.subset") != "small":
                continue
            artist = artists.setdefault(d["artist.id"], {
                "name": clean_html(d["artist.name"], 100) or f"Artist {d['artist.id']}",
                "bio": clean_html(d["artist.bio"], 5000),
                "albums": OrderedDict(),
            })
            album = artist["albums"].setdefault(d["album.id"], {
                "title": clean_html(d["album.title"], 200) or "Untitled album",
                "release_date": parse_date(d["album.date_released"], d["album.date_created"]),
                "tracks": [],
            })
            album["tracks"].append({
                "id": int(d["track_id"]),
                "title": clean_html(d["track.title"], 200) or "Untitled",
                "number": int(d["track.number"]) if d["track.number"].isdigit() else 0,
            })
    return artists


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--metadata", required=True, help="chemin de fma_metadata.zip")
    parser.add_argument("--audio", required=True, help="chemin de fma_small.zip")
    parser.add_argument("--limit", type=int, default=0, help="nombre maximum de titres à importer (0 = tous)")
    args = parser.parse_args()

    password = os.environ.get("SEED_ARTIST_PASSWORD")
    if not password or len(password) < 8:
        sys.exit("Définir SEED_ARTIST_PASSWORD (8 caractères minimum).")
    password_hash = hash_password(password)

    artists = read_small_tracks(args.metadata)
    print(f"{len(artists)} artistes dans fma_small")
    imported = skipped = 0

    with zipfile.ZipFile(args.audio) as audio_zip, get_sessionmaker()() as db:
        members = set(audio_zip.namelist())
        for fma_artist_id, a in artists.items():
            if args.limit and imported >= args.limit:
                break
            username = f"fma_artist_{fma_artist_id}"
            if db.scalar(select(User.id).where(User.username == username)):
                continue
            user = User(username=username, email=f"{username}@fma.invalid", password_hash=password_hash,
                        role="artist", is_verified=True)
            db.add(user)
            db.flush()
            artist = Artist(user_id=user.id, name=a["name"], bio=a["bio"], status="approved")
            db.add(artist)
            db.flush()
            saved_files = []
            try:
                for alb in a["albums"].values():
                    album = Album(artist_id=artist.id, title=alb["title"], status="published",
                                  release_date=alb["release_date"])
                    db.add(album)
                    db.flush()
                    tracks = sorted(alb["tracks"], key=lambda t: (t["number"] or 10**6, t["id"]))
                    added = 0
                    for position, t in enumerate(tracks, start=1):
                        tid = f"{t['id']:06d}"
                        member = f"fma_small/{tid[:3]}/{tid}.mp3"
                        if member not in members:
                            skipped += 1
                            continue
                        try:
                            with audio_zip.open(member) as src:
                                stored = storage.save_audio(src)
                        except AppError:
                            skipped += 1   # quelques extraits FMA sont corrompus
                            continue
                        saved_files.append(stored.file_path)
                        track = Track(album_id=album.id, title=t["title"], position=position,
                                      duration_s=stored.duration_s, file_path=stored.file_path, play_count=0)
                        db.add(track)
                        db.flush()
                        outbox.add(db, "track", track.id)
                        imported += 1
                        added += 1
                    if added:
                        outbox.add(db, "album", album.id)
                    else:
                        db.delete(album)   # aucun fichier lisible : pas d'album vide
                        db.flush()
                outbox.add(db, "artist", artist.id)
                db.commit()
            except Exception:
                db.rollback()
                for f in saved_files:
                    storage.delete_audio(f)
                raise
            print(f"\r{imported} titres importés, {skipped} ignorés", end="", flush=True)
    print(f"\nTerminé : {imported} titres importés, {skipped} ignorés. Le worker indexe dans Elasticsearch.")


if __name__ == "__main__":
    main()
