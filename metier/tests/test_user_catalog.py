from app.core.redis_client import PLAYS_HASH
from app.models import ListeningHistory, Track
from app.workers.tasks import flush_history, flush_play_counts, process_outbox
from conftest import login, png_bytes, published_album, register_verified_user


def test_search_likes_album_and_artist(client, redis_client, db_session, es):
    ids = published_album(client, redis_client, db_session, es, tracks=("DMTF", "Tití Me Preguntó"))
    register_verified_user(client, redis_client)

    res = client.get("/api/search", params={"q": "mauvais"}).json()
    assert {t["title"] for t in res["tracks"]} == {"DMTF", "Tití Me Preguntó"}
    assert [a["title"] for a in res["albums"]] == ["Titre album"]
    assert [a["name"] for a in res["artists"]] == ["Mauvaislapin"]
    assert client.get("/api/search", params={"q": "  "}).json() == {"tracks": [], "albums": [], "artists": []}

    track_id = ids["track_ids"][0]
    assert client.put(f"/api/tracks/{track_id}/like").status_code == 204
    assert client.put(f"/api/tracks/{track_id}/like").status_code == 204   # idempotent
    assert [t["id"] for t in client.get("/api/me/likes/tracks").json()] == [track_id]
    detail = client.get(f"/api/tracks/{track_id}").json()
    assert detail["liked"] and detail["like_count"] == 1 and detail["release_date"]

    album_id = ids["album_id"]
    client.put(f"/api/albums/{album_id}/like")
    liked = client.get("/api/me/likes/albums").json()
    assert liked[0]["id"] == album_id and liked[0]["track_count"] == 2 and liked[0]["liked"]
    album = client.get(f"/api/albums/{album_id}").json()
    assert album["like_count"] == 1 and len(album["tracks"]) == 2

    artist = client.get(f"/api/artists/{ids['artist_id']}").json()
    assert artist["bio"] == "Bio de test" and artist["albums"][0]["id"] == album_id

    client.delete(f"/api/tracks/{track_id}/like")
    assert client.get("/api/me/likes/tracks").json() == []


def test_playlists(client, redis_client, db_session, es):
    ids = published_album(client, redis_client, db_session, es, tracks=("A", "B"))
    register_verified_user(client, redis_client)
    t1, t2 = ids["track_ids"]

    r = client.post("/api/playlists", data={"name": "Goofy aaaaaah playlist", "track_ids": [str(t1)]})
    assert r.status_code == 201
    playlist = r.json()
    assert playlist["track_count"] == 1 and playlist["cover_url"] is None   # cover optionnelle

    assert client.post(f"/api/playlists/{playlist['id']}/tracks", json={"track_id": t2}).status_code == 204
    detail = client.get(f"/api/playlists/{playlist['id']}").json()
    assert [t["id"] for t in detail["tracks"]] == [t1, t2]
    assert detail["duration_s"] == sum(t["duration_s"] for t in detail["tracks"])

    r = client.patch(f"/api/playlists/{playlist['id']}", data={"name": "Renamed"},
                     files={"cover": ("c.png", png_bytes(), "image/png")})
    assert r.json()["name"] == "Renamed" and r.json()["cover_url"]

    client.delete(f"/api/playlists/{playlist['id']}/tracks/{t1}")
    assert client.get("/api/me/playlists").json()[0]["track_count"] == 1

    # Un autre user ne voit pas cette playlist
    register_verified_user(client, redis_client, "other", "other@example.com")
    assert client.get(f"/api/playlists/{playlist['id']}").status_code == 404
    login(client, "gusteau", "password123")
    assert client.delete(f"/api/playlists/{playlist['id']}").status_code == 204
    assert client.get("/api/me/playlists").json() == []


def test_featured_home_is_cached_and_invalidated(client, redis_client, db_session, es):
    ids = published_album(client, redis_client, db_session, es, tracks=("A", "B"))
    login(client, "admin", "adminpass")
    assert client.get("/api/admin/featured-playlist").json()["tracks"] == []
    client.post("/api/admin/featured-playlist/tracks", json={"track_id": ids["track_ids"][1]})

    register_verified_user(client, redis_client)
    assert [t["title"] for t in client.get("/api/home").json()] == ["B"]

    login(client, "admin", "adminpass")
    client.post("/api/admin/featured-playlist/tracks", json={"track_id": ids["track_ids"][0]})
    login(client, "gusteau", "password123")
    assert [t["title"] for t in client.get("/api/home").json()] == ["B", "A"]


def test_play_counter_and_stream(client, redis_client, db_session, es):
    ids = published_album(client, redis_client, db_session, es)
    track_id = ids["track_ids"][0]

    # L'artiste écoute uniquement ses titres
    login(client, "mauvaislapin", ids["password"])
    assert client.get(f"/api/stream/{track_id}").headers["x-accel-redirect"].startswith("/protected-audio/")

    register_verified_user(client, redis_client)
    r = client.get(f"/api/stream/{track_id}")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert client.get("/api/stream/9999").status_code == 404

    for _ in range(3):
        assert client.post(f"/api/tracks/{track_id}/play").status_code == 204
    assert redis_client.hget(PLAYS_HASH, str(track_id)) == "3"

    with db_session() as s:
        assert flush_play_counts(s, redis_client) == 1
        assert flush_history(s, redis_client) == 3
        assert s.get(Track, track_id).play_count == 3
        assert s.query(ListeningHistory).count() == 3
        process_outbox(s, es)
    assert es.docs["tracks"][str(track_id)]["play_count"] == 3
    assert client.get(f"/api/tracks/{track_id}").json()["play_count"] == 3


def test_artist_cannot_touch_other_artist_content(client, redis_client, db_session, es):
    first = published_album(client, redis_client, db_session, es, artist="premier")
    second = published_album(client, redis_client, db_session, es, artist="second")
    login(client, "second", second["password"])
    other_track = first["track_ids"][0]
    assert client.get(f"/api/stream/{other_track}").status_code == 404
    assert client.get(f"/api/artist/tracks/{other_track}").status_code == 404
    assert client.patch(f"/api/artist/tracks/{other_track}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/api/artist/tracks/{other_track}").status_code == 404
    assert client.delete(f"/api/artist/albums/{first['album_id']}").status_code == 404
    assert client.get(f"/api/stream/{second['track_ids'][0]}").status_code == 200


def test_artist_deletes_album_removes_everything(client, redis_client, db_session, es):
    ids = published_album(client, redis_client, db_session, es)
    register_verified_user(client, redis_client)
    client.put(f"/api/tracks/{ids['track_ids'][0]}/like")
    client.post("/api/playlists", data={"name": "P", "track_ids": [str(ids["track_ids"][0])]})

    login(client, "mauvaislapin", ids["password"])
    assert client.delete(f"/api/artist/albums/{ids['album_id']}").status_code == 204
    with db_session() as s:
        process_outbox(s, es)
    assert es.docs["tracks"] == {} and es.docs["albums"] == {}

    login(client, "gusteau", "password123")
    assert client.get("/api/me/likes/tracks").json() == []
    assert client.get("/api/me/playlists").json()[0]["track_count"] == 0
    assert client.get(f"/api/albums/{ids['album_id']}").status_code == 404
