import pytest

from eyened_orm import AuditLog, Feature
from eyened_orm.repositories.feature_repository import FeatureRepository
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401
from server.services.acting_user import ActingUser
from server.services.audit_service import AuditService
from server.services.feature_service import FeatureService


class _ExplodingRepo(FeatureRepository):
    """Second write raises after the first has been staged (design §2 defect (3))."""
    def replace_subfeatures(self, parent_id, sub_ids):
        raise RuntimeError("second call fails")


def test_first_write_rolls_back_when_second_fails(session):
    """When a later write raises, the earlier write and its audit row both vanish on rollback."""
    service = FeatureService(_ExplodingRepo(session), audit=AuditService(session))
    with pytest.raises(RuntimeError):
        service.create_feature("parent", [1], ActingUser(id=1, username="alice"))

    session.rollback()  # get_db does this in production on the propagated exception

    assert session.query(Feature).filter_by(FeatureName="parent").count() == 0
    assert session.query(AuditLog).count() == 0
    assert session.info.get("_audit_events", []) == []


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
