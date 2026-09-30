"""Flux audio : l'API vérifie les droits, Nginx envoie le fichier (X-Accel-Redirect)
et gère lui-même les requêtes Range (206 Partial Content)."""
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.deps import CurrentUser, Db, require_role
from app.core.errors import not_found
from app.repositories import catalog

router = APIRouter(tags=["stream"])

StreamRole = Annotated[CurrentUser, Depends(require_role("user", "artist"))]


@router.get("/stream/{track_id}")
def stream(track_id: int, user: StreamRole, db: Db) -> Response:
    if user.role == "user":
        # Un user écoute les titres publiés d'artistes validés
        row = catalog.get_visible_track(db, track_id)
    else:
        # Un artiste écoute uniquement ses propres titres
        row = catalog.get_track_any(db, track_id)
        if row and row[2].id != user.artist_id:
            row = None
    if not row:
        raise not_found("Track")
    return Response(
        status_code=200,
        headers={
            "X-Accel-Redirect": f"/protected-audio/{row[0].file_path}",
            "Content-Type": "audio/mpeg",
            "Cache-Control": "private, max-age=3600",
        },
    )
