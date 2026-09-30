from app.core.redis_client import MAIL_QUEUE
from conftest import last_token, login


def register(client, username="gusteau", email="gusteau@example.com", password="password123"):
    return client.post("/api/auth/register", json={"username": username, "email": email, "password": password})


def test_register_verify_login_logout(client, redis_client):
    assert register(client).status_code == 201
    assert redis_client.llen(MAIL_QUEUE) == 1   # email en file pour le worker

    r = login(client, "gusteau", "password123")
    assert r.status_code == 403 and r.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

    assert client.get("/api/auth/verify", params={"token": last_token(redis_client)}).json() == {"verified": True}
    r = login(client, "gusteau", "password123")
    assert r.status_code == 200
    assert r.json()["role"] == "user"
    assert "password" not in r.text and "hash" not in r.text

    me = client.get("/api/me")
    assert me.status_code == 200 and me.json()["username"] == "gusteau"

    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.clear()
    assert client.get("/api/me").json()["error"]["code"] == "AUTH_REQUIRED"


def test_login_with_email_and_wrong_password(client, redis_client):
    register(client)
    client.get("/api/auth/verify", params={"token": last_token(redis_client)})
    assert login(client, "GUSTEAU@example.com", "password123").status_code == 200
    r = login(client, "gusteau", "wrong-password")
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_verify_token_single_use(client, redis_client):
    register(client)
    token = last_token(redis_client)
    assert client.get("/api/auth/verify", params={"token": token}).status_code == 200
    r = client.get("/api/auth/verify", params={"token": token})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_TOKEN"


def test_register_validation_and_duplicates(client):
    assert register(client).status_code == 201
    assert register(client, email="other@example.com").json()["error"]["code"] == "USERNAME_TAKEN"
    assert register(client, username="other").json()["error"]["code"] == "EMAIL_TAKEN"
    r = register(client, username="short", email="s@example.com", password="1234567")
    assert r.status_code == 422 and "password" in r.json()["error"]["fields"]
    assert register(client, username="a@b", email="ab@example.com").status_code == 422


def test_resend_verification_rate_limited(client, redis_client):
    register(client)
    assert client.post("/api/auth/resend-verification", json={"email": "gusteau@example.com"}).status_code == 204
    r = client.post("/api/auth/resend-verification", json={"email": "gusteau@example.com"})
    assert r.status_code == 429
    # Adresse inconnue : même réponse, rien n'est révélé
    assert client.post("/api/auth/resend-verification", json={"email": "nobody@example.com"}).status_code == 204


def test_refresh_rotates_token(client, redis_client):
    register(client)
    client.get("/api/auth/verify", params={"token": last_token(redis_client)})
    login(client, "gusteau", "password123")
    old_refresh = client.cookies.get("refresh_token")
    assert client.post("/api/auth/refresh").status_code == 204
    assert client.cookies.get("refresh_token") != old_refresh
    # L'ancien refresh token ne marche plus
    client.cookies.clear()
    client.cookies.set("refresh_token", old_refresh, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401


def test_forgot_and_reset_password(client, redis_client):
    register(client)
    client.get("/api/auth/verify", params={"token": last_token(redis_client)})
    assert client.post("/api/auth/forgot-password", json={"email": "gusteau@example.com"}).status_code == 204
    token = last_token(redis_client, "reset")
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "newpassword1"}).status_code == 204
    assert login(client, "gusteau", "password123").status_code == 401
    assert login(client, "gusteau", "newpassword1").status_code == 200


def test_profile_username_and_password(client, redis_client):
    register(client)
    client.get("/api/auth/verify", params={"token": last_token(redis_client)})
    login(client, "gusteau", "password123")
    assert client.patch("/api/me", json={"username": "remy"}).json()["username"] == "remy"

    r = client.post("/api/me/password", json={"old_password": "bad", "new_password": "newpassword1"})
    assert r.json()["error"]["code"] == "WRONG_PASSWORD"
    assert client.post("/api/me/password", json={"old_password": "password123", "new_password": "newpassword1"}).status_code == 204
    # La session courante reste ouverte
    assert client.get("/api/me").status_code == 200
    assert login(client, "remy", "newpassword1").status_code == 200
