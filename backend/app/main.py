"""FastAPI application entrypoint.

``create_app()`` is the composition root: configure logging, build the app,
mount routers. ``app`` is the module-level instance uvicorn imports
(``app.main:app``).
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    app = FastAPI(
        title="Career Copilot API",
        version="0.0.0",
        debug=settings.debug,
    )
    app.include_router(health_router)
    return app


app = create_app()
