import json

from fastapi import FastAPI

from server.services.exceptions import (
    NotFoundError,
    ServiceError,
    register_exception_handlers,
    service_error_to_response,
)


def test_not_found_error_maps_to_404_response():
    """A NotFoundError should become an HTTP 404 carrying its message."""
    resp = service_error_to_response(NotFoundError("Patient 5 not found"))
    assert resp.status_code == 404
    assert json.loads(resp.body) == {"detail": "Patient 5 not found"}


def test_base_service_error_maps_to_500_response():
    """A plain ServiceError (no status override) falls back to HTTP 500."""
    resp = service_error_to_response(ServiceError("boom"))
    assert resp.status_code == 500
    assert json.loads(resp.body) == {"detail": "boom"}


def test_register_exception_handlers_registers_service_error_base():
    """Registering the ServiceError base makes every subclass dispatch through
    this one handler (incl. Step 2's future PermissionDeniedError), since
    Starlette resolves handlers by walking the exception's MRO."""
    app = FastAPI()
    register_exception_handlers(app)
    assert ServiceError in app.exception_handlers


def test_bad_request_error_maps_to_400_response():
    """BadRequestError maps to HTTP 400, carrying its detail message in the body."""
    from server.services.exceptions import BadRequestError

    resp = service_error_to_response(BadRequestError("Tag type must be Study"))
    assert resp.status_code == 400
    assert json.loads(resp.body) == {"detail": "Tag type must be Study"}


def test_conflict_error_maps_to_409_with_structured_detail():
    """ConflictError maps to HTTP 409 and preserves a structured (dict) detail body."""
    from server.services.exceptions import ConflictError

    detail = {
        "code": "FEATURE_HAS_SEGMENTATIONS",
        "message": "Cannot delete feature 'X' because it has 3 linked segmentation(s).",
        "segmentation_count": 3,
    }
    resp = service_error_to_response(ConflictError(detail))
    assert resp.status_code == 409
    assert json.loads(resp.body) == {"detail": detail}


def test_not_visible_error_maps_to_404_and_leaks_nothing():
    """The projects that failed go to the log, never to the body."""
    import json

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from eyened_orm.authz.errors import NotVisibleError
    from server.services.exceptions import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise NotVisibleError(
            actor_id=7, entity="Task", entity_id=70, projects={3, 9}
        )

    with TestClient(app) as client:
        resp = client.get("/boom")
    assert resp.status_code == 404
    body = json.dumps(resp.json())
    assert "3" not in body and "9" not in body and "Task" not in body


def test_permission_denied_error_maps_to_403():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from eyened_orm.authz.errors import PermissionDeniedError
    from server.services.exceptions import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise PermissionDeniedError(
            actor_id=7, entity="Segmentation", entity_id=5, projects={3}
        )

    with TestClient(app) as client:
        resp = client.get("/boom")
    assert resp.status_code == 403


def test_a_denial_is_logged_with_the_facts_the_response_omits(caplog):
    """A refusal is an action; this is the only record a boundary was tested."""
    import logging

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from eyened_orm.authz.errors import NotVisibleError
    from server.services.exceptions import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise NotVisibleError(actor_id=7, entity="Task", entity_id=70, projects={3})

    with caplog.at_level(logging.INFO, logger="eyened.authz"):
        with TestClient(app) as client:
            client.get("/boom")

    assert any(
        '"actor_id": 7' in r.message and '"entity": "Task"' in r.message
        for r in caplog.records
    )


def test_the_authorization_base_class_fails_closed_at_403():
    """A future subclass nobody added to _AUTHZ_STATUS must not become a 200."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from eyened_orm.authz.errors import AuthorizationError
    from server.services.exceptions import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise AuthorizationError(
            actor_id=7, entity="Task", entity_id=1, projects=set()
        )

    with TestClient(app) as client:
        assert client.get("/boom").status_code == 403
