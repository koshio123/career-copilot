"""Request-scoped context and security headers."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

RequestIdHeader = "X-Request-ID"

# The API only ever returns JSON, so lock everything down.
_API_CSP = "default-src 'none'; frame-ancestors 'none'"

# Swagger UI / ReDoc are HTML pages that pull assets from jsdelivr and run an
# inline bootstrap script. They get their own CSP.
_DOCS_PATHS = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src 'self' https://fastapi.tiangolo.com data:; "
    "font-src 'self' data:; "
    "worker-src 'self' blob:; "
    "frame-ancestors 'none'"
)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}

Handler = Callable[[Request], Awaitable[Response]]


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request id to the log context and echo it back."""

    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        request_id = request.headers.get(RequestIdHeader) or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers[RequestIdHeader] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        response = await call_next(request)
        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        csp = _DOCS_CSP if request.url.path in _DOCS_PATHS else _API_CSP
        response.headers.setdefault("Content-Security-Policy", csp)
        return response
