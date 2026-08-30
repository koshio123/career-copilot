"""Health endpoints.

``/healthz`` is a liveness probe: the process is up and serving. A readiness
probe (``/readyz``) that checks the database is added in Phase 02.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
