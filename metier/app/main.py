"""Point d'entrée de l'API MusicApp (couche métier).

Seule couche autorisée à parler à MySQL, Redis et Elasticsearch :
le client (présentation) ne passe que par cette API, derrière Nginx (/api/).
"""
from fastapi import FastAPI

from app.core.errors import install_error_handlers
from app.routers import admin, albums, artist, artists, auth, me, playlists, search, stream, tracks

app = FastAPI(
    title="MusicApp API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
install_error_handlers(app)

for module in (auth, me, tracks, albums, artists, search, playlists, stream, artist, admin):
    app.include_router(module.router, prefix="/api")


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
