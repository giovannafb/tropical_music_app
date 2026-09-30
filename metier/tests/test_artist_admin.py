from conftest import create_admin, last_token, login, mp3_bytes, png_bytes


def register_artist(client, r, username="mauvaislapin", password="artistpass1"):
    body = {"username": username, "email": f"{username}@example.com", "password": password,
            "artist_name": "MauvaisLapin", "bio": "Une bio"}
    assert client.post("/api/auth/register-artist", json=body).status_code == 201
    client.get("/api/auth/verify", params={"token": last_token(r)})


def test_artist_needs_admin_validation(client, redis_client, db_session):
    create_admin(db_session)
    register_artist(client, redis_client)
    r = login(client, "mauvaislapin", "artistpass1")
    assert r.status_code == 403 and r.json()["error"]["code"] == "ARTIST_PENDING"

    login(client, "admin", "adminpass")
    pending = client.get("/api/admin/artists").json()
    assert [a["name"] for a in pending] == ["MauvaisLapin"]
    r = client.post(f"/api/admin/artists/{pending[0]['id']}/reject", json={"reason": "Not original"})
    assert r.status_code == 204

    r = login(client, "mauvaislapin", "artistpass1")
    assert r.json()["error"] == {"code": "ARTIST_REJECTED", "message": "Your artist account was refused",
                                 "reason": "Not original"}


def test_album_draft_upload_publish(client, redis_client, db_session):
    create_admin(db_session)
    register_artist(client, redis_client)
    login(client, "admin", "adminpass")
    artist_id = client.get("/api/admin/artists").json()[0]["id"]
    client.post(f"/api/admin/artists/{artist_id}/approve")
    assert login(client, "mauvaislapin", "artistpass1").json()["artist"]["status"] == "approved"

    assert client.get("/api/artist/me/draft").json() is None
    album = client.post("/api/artist/albums", data={"title": "  Mon album  "}).json()
    assert album["title"] == "Mon album" and album["status"] == "draft"
    # Un seul brouillon
    assert client.post("/api/artist/albums", data={"title": "Autre"}).json()["error"]["code"] == "DRAFT_EXISTS"

    # Type réel vérifié : un faux MP3 est refusé
    r = client.post(f"/api/artist/albums/{album['id']}/tracks", files={"file": ("fake.mp3", b"not audio" * 100, "audio/mpeg")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_AUDIO"

    r = client.post(f"/api/artist/albums/{album['id']}/tracks", files={"file": ("My Song.mp3", mp3_bytes(), "audio/mpeg")})
    assert r.status_code == 201
    track = r.json()
    assert track["title"] == "My Song" and track["duration_s"] > 0

    assert client.patch(f"/api/artist/tracks/{track['id']}", json={"title": "DMTF"}).json()["title"] == "DMTF"

    # Cover obligatoire pour publier
    r = client.post(f"/api/artist/albums/{album['id']}/publish")
    assert r.json()["error"]["code"] == "COVER_REQUIRED"
    r = client.patch(f"/api/artist/albums/{album['id']}", files={"cover": ("c.png", png_bytes(), "image/png")})
    assert r.json()["cover_url"].endswith("_600.jpg")

    draft = client.get("/api/artist/me/draft").json()
    assert draft["id"] == album["id"] and [t["title"] for t in draft["tracks"]] == ["DMTF"]

    published = client.post(f"/api/artist/albums/{album['id']}/publish").json()
    assert published["status"] == "published" and published["release_date"]
    assert client.get("/api/artist/me/draft").json() is None
    assert [a["title"] for a in client.get("/api/artist/me/albums").json()] == ["Mon album"]
    assert [t["title"] for t in client.get("/api/artist/me/tracks").json()] == ["DMTF"]
    detail = client.get(f"/api/artist/tracks/{track['id']}").json()
    assert detail["release_date"] == published["release_date"]


def test_invalid_cover_rejected(client, redis_client, db_session):
    create_admin(db_session)
    register_artist(client, redis_client)
    login(client, "admin", "adminpass")
    client.post(f"/api/admin/artists/{client.get('/api/admin/artists').json()[0]['id']}/approve")
    login(client, "mauvaislapin", "artistpass1")
    r = client.post("/api/artist/albums", data={"title": "X"}, files={"cover": ("c.png", b"garbage", "image/png")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_IMAGE"


def test_roles_are_enforced(client, redis_client, db_session):
    create_admin(db_session)
    register_artist(client, redis_client)
    login(client, "admin", "adminpass")
    client.post(f"/api/admin/artists/{client.get('/api/admin/artists').json()[0]['id']}/approve")

    login(client, "mauvaislapin", "artistpass1")
    for path in ("/api/home", "/api/me/likes/tracks", "/api/me/playlists", "/api/search?q=a", "/api/admin/artists"):
        assert client.get(path).status_code == 403, path

    client.post("/api/auth/register", json={"username": "gusteau", "email": "g@example.com", "password": "password123"})
    client.get("/api/auth/verify", params={"token": last_token(redis_client)})
    login(client, "gusteau", "password123")
    for path in ("/api/artist/me/tracks", "/api/admin/artists", "/api/admin/featured-playlist"):
        assert client.get(path).status_code == 403, path

    client.cookies.clear()
    assert client.get("/api/home").status_code == 401
