"""Perry Budget — FastAPI app.

Serves the React SPA (/ui) and the JSON API (/api). The legacy Jinja UI has
been retired: the React app is the only frontend, and "/" redirects to it. This
also matters for security — every data path now sits behind the API's auth, so
exposing the add-on via a Cloudflare tunnel doesn't leak an ungated page.
"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from . import db, api as api_routes

BASE = os.path.dirname(__file__)
FRONTEND_DIST = os.path.join(BASE, "frontend_dist")
app = FastAPI(title="Perry Budget")

app.include_router(api_routes.router)

if os.path.isdir(os.path.join(FRONTEND_DIST, "assets")):
    app.mount("/ui/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
              name="ui-assets")


@app.on_event("startup")
def _startup():
    db.init_db()


def _spa_index(request: Request) -> HTMLResponse:
    """SPA shell with ingress-aware runtime config injected (see frontend/api.ts)."""
    ingress = request.headers.get("X-Ingress-Path", "")
    try:
        with open(os.path.join(FRONTEND_DIST, "index.html"), encoding="utf-8") as f:
            html = f.read()
    except OSError:
        return HTMLResponse("<h1>Perry Budget</h1><p>UI not built.</p>", status_code=503)
    html = html.replace("<head>", f"<head>\n    <base href=\"{ingress}/ui/\" />", 1)
    html = html.replace("__INGRESS_PATH__", ingress)
    html = html.replace("__ROUTER_BASE_PATH__", f"{ingress}/ui")
    return HTMLResponse(html)


_MEDIA = {".webmanifest": "application/manifest+json"}


@app.get("/")
def root(request: Request):
    return RedirectResponse(url=f"{request.headers.get('X-Ingress-Path', '')}/ui/")


# Friendly redirects for the retired Jinja paths.
@app.get("/budgets")
def _r_budgets(request: Request):
    return RedirectResponse(url=f"{request.headers.get('X-Ingress-Path', '')}/ui/budgets")


@app.get("/manage")
def _r_manage(request: Request):
    return RedirectResponse(url=f"{request.headers.get('X-Ingress-Path', '')}/ui/manage")


@app.get("/term")
def _r_term(request: Request):
    return RedirectResponse(url=f"{request.headers.get('X-Ingress-Path', '')}/ui/terminal")


@app.get("/ui")
@app.get("/ui/{path:path}")
def spa(request: Request, path: str = ""):
    # Serve real files that live in the dist root (manifest, sw.js, icons);
    # everything else is a client route -> return the SPA shell.
    if path:
        candidate = os.path.normpath(os.path.join(FRONTEND_DIST, path))
        if candidate.startswith(FRONTEND_DIST) and os.path.isfile(candidate):
            ext = os.path.splitext(candidate)[1]
            return FileResponse(candidate, media_type=_MEDIA.get(ext))
    return _spa_index(request)
