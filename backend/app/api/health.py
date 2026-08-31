"""Health endpoints.

``/healthz`` — liveness: the process is up.
``/readyz``  — readiness: dependencies (the database) are reachable.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Response
from sqlalchemy import text

from app.db.session import get_engine

router = APIRouter(tags=["meta"])
log = structlog.get_logger(__name__)


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, object]:
    checks: dict[str, str] = {}
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        log.warning("readyz.database_failed", error=str(exc))
        checks["database"] = "error"

    ready = all(v == "ok" for v in checks.values())
    if not ready:
        response.status_code = 503
    return {"status": "ready" if ready else "not ready", "checks": checks}
