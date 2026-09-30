"""Tests de charge (doc §10) : scénarios « rechercher », « écouter », « liker », « ouvrir une playlist ».

Lancement (stack Docker démarrée, compte user existant) :
    set LOCUST_LOGIN=gusteau
    set LOCUST_PASSWORD=...
    locust -f tests/load/locustfile.py --host http://localhost

Comparer latence p95 et requêtes/s : 1 vs 3 instances d'API, 0 vs 2 répliques ES, avec et sans cache Redis.
"""
import os
import random

from locust import HttpUser, between, task

SEARCH_TERMS = os.environ.get("LOCUST_TERMS", "love,night,the,rock,dream,blue,fire,mauvais").split(",")


class Listener(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.tracks = []
        self.login()

    def login(self):
        res = self.client.post("/api/auth/login", json={
            "login": os.environ["LOCUST_LOGIN"], "password": os.environ["LOCUST_PASSWORD"],
        }, name="/api/auth/login")
        # Les cookies « Secure » ne sont pas renvoyés par le client HTTP sur http:// :
        # on les renvoie explicitement dans l'en-tête Cookie.
        self.cookie = "; ".join(f"{c.name}={c.value}" for c in res.cookies)

    def call(self, method, path, name=None, **kwargs):
        headers = {"Cookie": self.cookie, **kwargs.pop("headers", {})}
        res = self.client.request(method, path, headers=headers, name=name or path, **kwargs)
        if res.status_code == 401:   # JWT expiré (15 min) : nouvelle connexion
            self.login()
            headers["Cookie"] = self.cookie
            res = self.client.request(method, path, headers=headers, name=name or path, **kwargs)
        return res

    def pick_track(self):
        if not self.tracks:
            res = self.call("GET", "/api/home")
            self.tracks = [t["id"] for t in res.json()] if res.ok else []
        return random.choice(self.tracks) if self.tracks else None

    @task(4)
    def rechercher(self):
        self.call("GET", f"/api/search?q={random.choice(SEARCH_TERMS)}", name="/api/search")

    @task(3)
    def ecouter(self):
        track_id = self.pick_track()
        if track_id is None:
            return
        self.call("GET", f"/api/stream/{track_id}", name="/api/stream/[id]", headers={"Range": "bytes=0-262143"})
        self.call("POST", f"/api/tracks/{track_id}/play", name="/api/tracks/[id]/play")

    @task(2)
    def liker(self):
        track_id = self.pick_track()
        if track_id is None:
            return
        self.call("PUT", f"/api/tracks/{track_id}/like", name="/api/tracks/[id]/like")
        self.call("DELETE", f"/api/tracks/{track_id}/like", name="/api/tracks/[id]/like")

    @task(2)
    def ouvrir_une_playlist(self):
        res = self.call("GET", "/api/me/playlists")
        if res.ok and res.json():
            playlist = random.choice(res.json())
            self.call("GET", f"/api/playlists/{playlist['id']}", name="/api/playlists/[id]")
