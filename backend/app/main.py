"""FastAPI application entrypoint.

``create_app()`` is the composition root: configure logging, build the app,
register middleware / error handlers / routers. ``app`` is the module-level
instance uvicorn imports (``app.main:app``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1 import router as v1_router
from app.auth.dynamo import ensure_tables
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.queue.bootstrap import ensure_queues
from app.storage.bootstrap import ensure_bucket


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.is_local:
        # dev/prod resources are created by Terraform (Phase 10).
        await ensure_tables()
        await ensure_queues()
        await ensure_bucket()
    yield


def create_app() -> FastAPI:
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    app = FastAPI(
        title="Career Copilot API",
        version="0.0.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(v1_router)
    return app


app = create_app()
