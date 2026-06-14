"""JSON API for the React frontend.

Additive layer: exposes the existing budget engine over JSON and coexists with
the Jinja UI during the migration. Money is integer cents end to end.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from . import budget, auth
from .meta import VERSION

router = APIRouter(prefix="/api")


# ---- auth ----------------------------------------------------------------

class LoginBody(BaseModel):
    username: str
    password: str


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


def require_user(request: Request):
    """FastAPI dependency: 401 unless a valid session cookie is present."""
    user = auth.get_session_user(request.cookies.get(auth.COOKIE_NAME))
    if not user:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


def _set_session_cookie(request: Request, response: Response, token: str):
    # Secure only when the request arrived over HTTPS (ingress / tunnel), so the
    # standalone http :8099 path keeps working in dev/LAN.
    secure = request.url.scheme == "https" or \
        request.headers.get("x-forwarded-proto", "") == "https"
    response.set_cookie(
        auth.COOKIE_NAME, token, max_age=auth.SESSION_TTL, httponly=True,
        samesite="lax", secure=secure, path="/")


@router.post("/login")
def login(request: Request, response: Response, body: LoginBody):
    key = f"{body.username.strip().lower()}|{request.client.host if request.client else '?'}"
    if auth.throttled(key):
        raise HTTPException(status_code=429, detail="too many attempts; wait a few minutes")
    user = auth.authenticate(body.username, body.password)
    if not user:
        auth.record_fail(key)
        raise HTTPException(status_code=401, detail="invalid username or password")
    auth.clear_fails(key)
    token = auth.create_session(user["id"])
    _set_session_cookie(request, response, token)
    return {"user": auth.public_user(user)}


@router.post("/logout")
def logout(request: Request, response: Response):
    auth.delete_session(request.cookies.get(auth.COOKIE_NAME))
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = auth.get_session_user(request.cookies.get(auth.COOKIE_NAME))
    return {"user": auth.public_user(user) if user else None}


@router.post("/change-password")
def change_password(request: Request, body: ChangePasswordBody, user=Depends(require_user)):
    if not auth.verify_password(body.current_password, user["password_salt"], user["password_hash"]):
        raise HTTPException(status_code=400, detail="current password is incorrect")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="new password must be at least 6 characters")
    auth.set_password(user["id"], body.new_password)
    return {"ok": True}


# ---- health --------------------------------------------------------------

@router.get("/health")
def health():
    """Liveness + a couple of engine values, used by the SPA to confirm the
    runtime config (ingress path, API base) is wired correctly."""
    y, m = budget.current_period()
    return {
        "ok": True,
        "app": "perry_budget",
        "version": VERSION,
        "now": budget.now_ct().isoformat(),
        "period": {"year": y, "month": m},
    }
