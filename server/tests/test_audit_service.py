import json
import logging

import pytest

from eyened_orm import AuditLog
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401
from server.services.acting_user import ActingUser
from server.services.audit_service import AuditService


def _actor() -> ActingUser:
    return ActingUser(id=1, username="alice")


@pytest.fixture(autouse=True)
def _isolate_audit_logger():
    """Keep these caplog tests independent of global logger state. Task 4's
    configure_audit_logging() sets propagate=False on the shared eyened.audit
    logger, and (collected first, alphabetically) would otherwise stop caplog's
    root handler from ever seeing audit events. Force propagate=True, then restore."""
    audit = logging.getLogger("eyened.audit")
    saved = (audit.propagate, audit.handlers[:], audit.level)
    audit.propagate = True
    audit.handlers = []
    yield
    audit.propagate, audit.handlers, audit.level = saved


def test_record_writes_audit_row_in_session(session):
    """record() flushes exactly one AuditLog row with the given fields."""
    AuditService(session).record(
        action="INSERT", entity="Feature", actor=_actor(),
        entity_id=7, changes={"name": "Retina"},
    )
    rows = session.query(AuditLog).all()
    assert len(rows) == 1
    assert rows[0].Action == "INSERT"
    assert rows[0].Entity == "Feature"
    assert rows[0].ActorID == 1
    assert rows[0].EntityID == "7"
    assert rows[0].Changes == {"name": "Retina"}


def test_record_trusted_path_has_no_actor(session):
    """A trusted-path record has ActorID NULL and TrustedPath set."""
    AuditService(session).record(
        action="INSERT", entity="ImageInstance", trusted_path="cli:import",
    )
    row = session.query(AuditLog).one()
    assert row.ActorID is None
    assert row.TrustedPath == "cli:import"


def test_commit_emits_one_stdout_event_mirroring_the_row(session, caplog):
    """A committed record drains exactly one JSON event to the eyened.audit logger."""
    with caplog.at_level(logging.INFO, logger="eyened.audit"):
        AuditService(session).record(
            action="UPDATE", entity="Feature", actor=_actor(), entity_id=7,
        )
        session.commit()

    events = [json.loads(r.getMessage()) for r in caplog.records
              if r.name == "eyened.audit"]
    assert len(events) == 1
    assert events[0]["action"] == "UPDATE"
    assert events[0]["entity"] == "Feature"
    assert events[0]["entity_id"] == "7"
    assert events[0]["actor_id"] == 1


def test_rollback_emits_no_stdout_event(session, caplog):
    """A rolled-back record leaves no AuditLog row and emits no stdout event."""
    with caplog.at_level(logging.INFO, logger="eyened.audit"):
        AuditService(session).record(action="DELETE", entity="Feature", entity_id=7)
        session.rollback()

    assert session.query(AuditLog).count() == 0
    assert [r for r in caplog.records if r.name == "eyened.audit"] == []


def test_disabled_service_records_nothing(session):
    """enabled=False makes record() a no-op (no row, no buffer)."""
    AuditService(session, enabled=False).record(action="INSERT", entity="Feature")
    assert session.query(AuditLog).count() == 0
    assert session.info.get("_audit_events", []) == []


def test_diff_maps_changed_scalar_to_old_new(session):
    """diff() reports a changed column as {"old": …, "new": …} (called before flush)."""
    from eyened_orm import Feature

    feature = Feature(FeatureName="old")
    session.add(feature)
    session.flush()  # baseline persisted state for the history comparison

    feature.FeatureName = "new"
    assert AuditService._diff_from_history(feature, "FeatureName") == {
        "FeatureName": {"old": "old", "new": "new"}
    }


def test_diff_omits_fields_set_to_their_current_value(session):
    """A field reassigned its existing value is not reported as a change."""
    from eyened_orm import Feature

    feature = Feature(FeatureName="stable")
    session.add(feature)
    session.flush()

    feature.FeatureName = "stable"
    assert AuditService._diff_from_history(feature, "FeatureName") == {}


def test_record_persists_enum_member_in_changes_as_its_value(session):
    """A raw (non-str) Enum member in changes flushes clean and is stored as .value, not the object."""
    from eyened_orm.tag import TagType

    AuditService(session).record(
        action="UPDATE", entity="Tag", actor=_actor(), entity_id=1,
        changes={"tag_type": TagType.ImageInstance},
    )
    row = session.query(AuditLog).one()
    assert row.Changes == {"tag_type": "ImageInstance"}


def test_record_persists_datetime_in_changes_as_isoformat(session):
    """A raw datetime in changes flushes clean and is stored as an ISO 8601 string."""
    from datetime import datetime, timezone

    ts = datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc)
    AuditService(session).record(
        action="UPDATE", entity="Feature", actor=_actor(), entity_id=1,
        changes={"updated_at": ts},
    )
    row = session.query(AuditLog).one()
    assert row.Changes == {"updated_at": ts.isoformat()}
