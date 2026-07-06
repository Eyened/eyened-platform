import json

from fastapi import FastAPI

from server.services.exceptions import (
    NotFoundError,
    ServiceError,
    register_exception_handlers,
    service_error_to_response,
)


def test_not_found_error_maps_to_404_response():
    # A NotFoundError should become an HTTP 404 carrying its message.
    resp = service_error_to_response(NotFoundError("Patient 5 not found"))
    assert resp.status_code == 404
    assert json.loads(resp.body) == {"detail": "Patient 5 not found"}


def test_base_service_error_maps_to_500_response():
    # A plain ServiceError (no status override) falls back to HTTP 500.
    resp = service_error_to_response(ServiceError("boom"))
    assert resp.status_code == 500
    assert json.loads(resp.body) == {"detail": "boom"}


def test_register_exception_handlers_registers_service_error_base():
    # Registering the ServiceError base is what makes every subclass (incl.
    # Step 2's future PermissionDeniedError) dispatch through this one handler,
    # since Starlette resolves handlers by walking the exception's MRO.
    app = FastAPI()
    register_exception_handlers(app)
    assert ServiceError in app.exception_handlers
