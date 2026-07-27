import pytest
from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import AuditLog, Feature
from eyened_orm.repositories.feature_repository import FeatureRepository
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401
from server.db import get_db
from server.services.acting_user import ActingUser
from server.services.audit_service import AuditService, get_audit_service
from server.services.exceptions import NotFoundError
from server.services.feature_service import FeatureService, get_feature_service


class _ExplodingRepo(FeatureRepository):
    """Second write raises after the first has been staged (design §2 defect (3))."""
    def replace_subfeatures(self, parent_id, sub_ids):
        raise RuntimeError("second call fails")


def test_first_write_rolls_back_when_second_fails(session):
    """When a later write raises, the earlier already-flushed write vanishes on rollback."""
    service = FeatureService(_ExplodingRepo(session), audit=AuditService(session))
    with pytest.raises(RuntimeError):
        service.create_feature("parent", [1], ActingUser(id=1, username="alice"))

    session.rollback()  # get_db does this in production on the propagated exception

    assert session.query(Feature).filter_by(FeatureName="parent").count() == 0


def test_prior_audit_row_rolls_back_with_a_later_failed_write(session):
    """An audit row staged before a later failure is discarded on rollback too (not just the failing write's own)."""
    AuditService(session).record(
        action="INSERT", entity="Feature", actor=ActingUser(id=1, username="alice"),
        entity_id=1, changes={"name": "pre-existing"},
    )

    service = FeatureService(_ExplodingRepo(session), audit=AuditService(session))
    with pytest.raises(RuntimeError):
        service.create_feature("parent", [1], ActingUser(id=1, username="alice"))

    session.rollback()  # get_db does this in production on the propagated exception

    assert session.query(AuditLog).count() == 0
    assert session.info.get("_audit_events", []) == []


class _NotFoundAfterWriteRepo(FeatureRepository):
    """Second write raises a domain ServiceError after the first has been
    staged -- unlike _ExplodingRepo's plain RuntimeError above, this exercises
    the ServiceError exception-handler path (an intended HTTP status), not
    the generic 500 handler."""
    def replace_subfeatures(self, parent_id, sub_ids):
        raise NotFoundError("subfeature not found")


def test_domain_error_mid_request_rolls_back_and_returns_its_status(client, session):
    """A NotFoundError raised mid-request, after a staged write, through a
    real HTTP request: the write (and any audit row) rolls back and the
    client still gets the error's intended status -- design §4's "error paths
    preserve intent", pinned end-to-end against whatever FastAPI version is
    installed (dependency-exit-vs-exception-handler ordering changed in
    0.106)."""
    from server.main import app_api

    def _failing_feature_service(db: Session = Depends(get_db)) -> FeatureService:
        return FeatureService(_NotFoundAfterWriteRepo(db), audit=get_audit_service(db))

    app_api.dependency_overrides[get_feature_service] = _failing_feature_service
    try:
        response = client.post(
            "/features", json={"name": "should-not-persist", "subfeature_ids": [1]}
        )
    finally:
        app_api.dependency_overrides.pop(get_feature_service, None)

    assert response.status_code == 404, response.text
    assert (
        session.query(Feature).filter_by(FeatureName="should-not-persist").count() == 0
    )
    assert session.query(AuditLog).count() == 0
