from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.deps import REFRESH_COOKIE, Db, Redis
from app.models import Artist, User
from app.schemas import EmailIn, LoginIn, MeOut, RegisterArtistIn, RegisterIn, ResetPasswordIn
from app.services import auth, sessions
from app.services.profile import me_out

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Db, r: Redis) -> dict:
    user = auth.register_user(db, r, body.username, body.email, body.password)
    return {"email": user.email}


@router.post("/register-artist", status_code=201)
def register_artist(body: RegisterArtistIn, db: Db, r: Redis) -> dict:
    user = auth.register_artist(db, r, body.username, body.email, body.password, body.artist_name, body.bio)
    return {"email": user.email}


@router.post("/login")
def login(body: LoginIn, response: Response, db: Db, r: Redis) -> MeOut:
    user, artist = auth.authenticate(db, body.login, body.password)
    sessions.open_session(r, response, user.id, user.role, artist.id if artist else None)
    return me_out(user, artist)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, r: Redis) -> None:
    sessions.close_session(r, response, request.cookies.get(REFRESH_COOKIE))


@router.post("/refresh", status_code=204)
def refresh(request: Request, response: Response, db: Db, r: Redis):
    user_id = sessions.consume_refresh(r, request.cookies.get(REFRESH_COOKIE))
    user = db.get(User, user_id) if user_id else None
    artist = db.scalar(select(Artist).where(Artist.user_id == user.id)) if user and user.role == "artist" else None
    still_allowed = user and user.is_verified and (user.role != "artist" or (artist and artist.status == "approved"))
    if not still_allowed:
        failed = JSONResponse(status_code=401, content={"error": {"code": "AUTH_REQUIRED", "message": "Please log in"}})
        sessions.clear_cookies(failed)
        return failed
    sessions.open_session(r, response, user.id, user.role, artist.id if artist else None)
    return None


@router.get("/verify")
def verify(token: str, db: Db) -> dict:
    auth.verify_email(db, token)
    return {"verified": True}


@router.post("/resend-verification", status_code=204)
def resend_verification(body: EmailIn, db: Db, r: Redis) -> None:
    auth.resend_verification(db, r, body.email)


@router.post("/forgot-password", status_code=204)
def forgot_password(body: EmailIn, db: Db, r: Redis) -> None:
    auth.forgot_password(db, r, body.email)


@router.post("/reset-password", status_code=204)
def reset_password(body: ResetPasswordIn, db: Db, r: Redis) -> None:
    auth.reset_password(db, r, body.token, body.password)
