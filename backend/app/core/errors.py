"""Problem Details (RFC 9457) error handling.

Every error response is ``application/problem+json`` with a stable machine
``code``. Domain code raises ``AppError`` subclasses; framework errors are
mapped by the handlers registered via ``register_exception_handlers``.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

log = structlog.get_logger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"


class AppError(Exception):
    status: int = 500
    code: str = "internal-error"
    title: str = "Internal Server Error"

    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        self.extra = extra


class NotFoundError(AppError):
    status = 404
    code = "not-found"
    title = "Not Found"


class AuthRequiredError(AppError):
    status = 401
    code = "authentication-required"
    title = "Authentication Required"


class CsrfError(AppError):
    status = 403
    code = "csrf-check-failed"
    title = "CSRF Check Failed"


class RateLimitedError(AppError):
    status = 429
    code = "rate-limited"
    title = "Too Many Requests"


class ServiceUnavailableError(AppError):
    status = 503
    code = "service-unavailable"
    title = "Service Unavailable"


class ValidationError(AppError):
    status = 422
    code = "validation-error"
    title = "Validation Error"


def problem(
    request: Request,
    *,
    status: int,
    title: str,
    code: str,
    detail: str,
    **extra: Any,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
    }
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_CONTENT_TYPE)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return problem(
            request,
            status=exc.status,
            title=exc.title,
            code=exc.code,
            detail=exc.detail,
            **exc.extra,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem(
            request,
            status=422,
            title="Validation Error",
            code="validation-error",
            detail="One or more fields are invalid.",
            errors=[
                {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
            ],
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(
            request,
            status=exc.status_code,
            title=str(exc.detail),
            code="http-error",
            detail=str(exc.detail),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_exception", path=request.url.path)
        return problem(
            request,
            status=500,
            title="Internal Server Error",
            code="internal-error",
            detail="An unexpected error occurred.",
        )
