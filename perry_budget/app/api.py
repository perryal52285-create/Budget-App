"""JSON API for the React frontend.

Additive layer: it exposes the existing budget engine over JSON and coexists
with the Jinja UI during the migration. Money is integer cents end to end.
"""
from fastapi import APIRouter

from . import budget
from .meta import VERSION

router = APIRouter(prefix="/api")


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
