"""Domain exceptions raised by the service layer, plus their HTTP mapping.

Services raise these instead of ``HTTPException``. A single FastAPI handler
(registered via ``register_exception_handlers``) maps them to responses, so
new exception types (e.g. RBAC's future ``PermissionDeniedError``) only need
a subclass with a ``status_code`` — no per-route wiring.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ServiceError(Exception):
    """Base class for service-layer errors. Maps to HTTP ``status_code``."""

    status_code: int = 500

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class NotFoundError(ServiceError):
    """A requested entity does not exist."""

    status_code = 404


class BadRequestError(ServiceError):
    """A request violates a business precondition (maps to HTTP 400).

    Distinct from ``pydantic.ValidationError`` (request-schema validation,
    handled by FastAPI before the Service runs); this is a domain-rule
    violation raised by the Service itself.
    """

    status_code = 400


def service_error_to_response(exc: ServiceError) -> JSONResponse:
    """Map a ServiceError to the JSON error response shape used by the API."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def register_exception_handlers(app: FastAPI) -> None:
    """Register a single handler that maps every ServiceError subclass.

    Starlette resolves handlers by walking the exception's MRO, so registering
    the ``ServiceError`` base catches all subclasses; each subclass's
    ``status_code`` drives the response.
    """

    @app.exception_handler(ServiceError)
    async def _handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
        return service_error_to_response(exc)
