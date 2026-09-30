"""Tests de la couche métier sans infrastructure :
SQLite en mémoire (à la place de MySQL), fakeredis (Redis) et un faux Elasticsearch."""
import atexit
import io
import json
import os
import re
import shutil
import sys
import tempfile

MEDIA = tempfile.mkdtemp(prefix="musicapp-media-")
atexit.register(shutil.rmtree, MEDIA, ignore_errors=True)
os.environ.update({
    "DATABASE_URL": "sqlite://",
    "JWT_SECRET": "test-secret-key-with-enough-length-0123456789",
    "MEDIA_ROOT": MEDIA,
    "COOKIE_SECURE": "false",   # le client de test parle en HTTP
    "PUBLIC_URL": "http://testserver",
})
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core import db as core_db  # noqa: E402
from app.core.redis_client import MAIL_QUEUE, get_redis  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import FEATURED_PLAYLIST_KEY, AppSetting, Base, Playlist, User  # noqa: E402
from app.repositories.search import ALIASES, get_es  # noqa: E402

SAMPLE_MP3 = os.path.join(os.path.dirname(__file__), "fixtures", "sample.mp3")


class FakeEs:
    """Faux Elasticsearch : garde les documents en mémoire, recherche par sous-chaîne."""

    def __init__(self):
        self.docs = {alias: {} for alias in ALIASES}

    def bulk(self, operations, refresh=False):
        items, i = [], 0
        while i < len(operations):
            action, meta = next(iter(operations[i].items()))
            index = meta["_index"]
            if action == "index":
                self.docs[index][meta["_id"]] = operations[i + 1]
                i += 2
            else:
                self.docs[index].pop(meta["_id"], None)
                i += 1
            items.append({action: {"status": 200}})
        return {"errors": False, "items": items}

    def msearch(self, searches):
        responses = []
        for header, body in zip(searches[::2], searches[1::2]):
            alias = header["index"]
            q = body["query"]
            q = q.get("function_score", {}).get("query", q)["multi_match"]["query"].lower()
            hits = [
                {"_id": doc_id, "_source": doc}
                for doc_id, doc in self.docs[alias].items()
                if q in json.dumps(doc, ensure_ascii=False).lower()
            ][: body["size"]]
            responses.append({"hits": {"hits": hits}})
        return {"responses": responses}


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    yield maker
    engine.dispose()


@pytest.fixture()
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture()
def es():
    return FakeEs()


@pytest.fixture()
def client(db_session, redis_client, es):
    def _db():
        s = db_session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[core_db.get_db] = _db
    app.dependency_overrides[get_redis] = lambda: redis_client
    app.dependency_overrides[get_es] = lambda: es
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------- Aides ----------

def last_token(r, kind: str = "verify") -> str:
    """Récupère le token du dernier email en file (lien #/verify?token=… ou #/reset-password?token=…)."""
    mails = [json.loads(m) for m in r.lrange(MAIL_QUEUE, 0, -1)]
    path = "verify" if kind == "verify" else "reset-password"
    for mail in reversed(mails):
        m = re.search(rf"#/{path}\?token=([\w\-]+)", mail["body"])
        if m:
            return m.group(1)
    raise AssertionError("aucun email trouvé")


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 500), (69, 147, 154)).save(buf, "PNG")
    return buf.getvalue()


def mp3_bytes() -> bytes:
    with open(SAMPLE_MP3, "rb") as f:
        return f.read()


def create_admin(db_session, username="admin", password="adminpass"):
    with db_session() as s:
        admin = User(username=username, email=f"{username}@example.com", password_hash=hash_password(password),
                     role="admin", is_verified=True)
        s.add(admin)
        s.flush()
        playlist = Playlist(user_id=admin.id, name="Featured")
        s.add(playlist)
        s.flush()
        s.add(AppSetting(key=FEATURED_PLAYLIST_KEY, value=str(playlist.id)))
        s.commit()
        return admin.id, playlist.id


def login(client, login_name, password):
    client.cookies.clear()
    return client.post("/api/auth/login", json={"login": login_name, "password": password})


def register_verified_user(client, r, username="gusteau", email="gusteau@example.com", password="password123"):
    assert client.post("/api/auth/register", json={"username": username, "email": email, "password": password}).status_code == 201
    assert client.get("/api/auth/verify", params={"token": last_token(r)}).status_code == 200
    assert login(client, username, password).status_code == 200


def published_album(client, r, db_session, es, artist="mauvaislapin", title="Titre album", tracks=("DMTF",)):
    """Crée un artiste validé avec un album publié ; renvoie les ids utiles. Laisse l'admin connecté."""
    from app.workers.tasks import process_outbox

    password = "artistpass1"
    client.cookies.clear()
    body = {"username": artist, "email": f"{artist}@example.com", "password": password,
            "artist_name": artist.capitalize(), "bio": "Bio de test"}
    assert client.post("/api/auth/register-artist", json=body).status_code == 201
    client.get("/api/auth/verify", params={"token": last_token(r)})
    with db_session() as s:
        admin = s.query(User).filter_by(role="admin").first()
    if admin is None:
        create_admin(db_session)
    assert login(client, "admin", "adminpass").status_code == 200
    pending = client.get("/api/admin/artists").json()
    artist_id = next(a["id"] for a in pending if a["username"] == artist)
    assert client.post(f"/api/admin/artists/{artist_id}/approve").status_code == 204
    assert login(client, artist, password).status_code == 200
    album = client.post("/api/artist/albums", data={"title": title},
                        files={"cover": ("cover.png", png_bytes(), "image/png")}).json()
    track_ids = []
    for name in tracks:
        t = client.post(f"/api/artist/albums/{album['id']}/tracks", data={"title": name},
                        files={"file": ("song.mp3", mp3_bytes(), "audio/mpeg")})
        assert t.status_code == 201, t.text
        track_ids.append(t.json()["id"])
    assert client.post(f"/api/artist/albums/{album['id']}/publish").status_code == 200
    with db_session() as s:
        process_outbox(s, es)
    return {"artist_id": artist_id, "album_id": album["id"], "track_ids": track_ids, "password": password}
