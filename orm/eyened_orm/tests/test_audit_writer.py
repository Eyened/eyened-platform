"""The authoritative AuditLog row writer: both attribution directions, pinned."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from eyened_orm import AuditLog
from eyened_orm.audit_writer import AuditWriter
from eyened_orm.authz.actor import ActingAdmin, TrustedPath


def test_a_trusted_path_writes_its_full_name_and_no_actor(session):
    """TrustedPath carries the whole name -- the writer adds no prefix.

    `auth:register` is why: a production trusted path already exists that is
    not `eorm`, so no single prefix belongs here.
    """
    AuditWriter(session).write(
        actor=TrustedPath("auth:register"), action="INSERT", entity="Creator"
    )
    row = session.scalars(select(AuditLog)).one()
    assert row.TrustedPath == "auth:register"
    assert row.ActorID is None


def test_an_acting_admin_writes_its_id_and_no_trusted_path(session):
    """The mirror direction. Pinning only one leaves the other free to drift."""
    AuditWriter(session).write(
        actor=ActingAdmin(42), action="UPDATE", entity="Creator"
    )
    row = session.scalars(select(AuditLog)).one()
    assert row.ActorID == 42
    assert row.TrustedPath is None


def test_an_unrecognised_actor_raises_rather_than_writing_an_unattributed_row(session):
    """No default branch: a third variant added without a case here must fail
    loudly, not write a row with both columns NULL."""
    with pytest.raises(TypeError, match="unrecognised Actor"):
        AuditWriter(session).write(actor="root", action="UPDATE", entity="Creator")
    assert session.scalars(select(AuditLog)).all() == []


def test_the_row_carries_project_id_and_a_stringified_entity_id(session):
    """`audit_trusted` dropped ProjectID entirely; EntityID is a String column."""
    AuditWriter(session).write(
        actor=TrustedPath("eorm grant"),
        action="INSERT",
        entity="ProjectMember",
        entity_id=7,
        project_id=3,
    )
    row = session.scalars(select(AuditLog)).one()
    assert row.EntityID == "7"
    assert row.ProjectID == 3


def test_the_row_is_flushed_so_its_primary_key_is_assigned(session):
    """The caller buffers the row for the stdout mirror and needs its id."""
    row = AuditWriter(session).write(
        actor=TrustedPath("eorm grant"), action="INSERT", entity="ProjectMember"
    )
    assert row.AuditLogID is not None


def test_the_writer_stamps_the_timestamp_itself(session):
    """Behavior change 3. Not left to the column default: the returned row must
    already carry the value any mirror derived from it will report, and
    `audit_trusted` returned a row with nothing to read."""
    before = datetime.now(timezone.utc)
    row = AuditWriter(session).write(
        actor=TrustedPath("eorm grant"), action="INSERT", entity="ProjectMember"
    )
    after = datetime.now(timezone.utc)
    assert before <= row.Timestamp <= after


class _Grade(enum.Enum):
    good = "good"


def test_changes_are_normalised_so_an_enum_reaches_the_json_column(session):
    """A raw Enum member in Changes raises StatementError on flush -- AuditLog.Changes
    is a stock JSON column with no `default=`. The round-trip also covers enums
    nested inside the {"old": ..., "new": ...} shape diff() produces."""
    AuditWriter(session).write(
        actor=TrustedPath("eorm grant"),
        action="UPDATE",
        entity="Tag",
        changes={"grade": {"old": _Grade.good, "new": _Grade.good}},
    )
    row = session.scalars(select(AuditLog)).one()
    assert row.Changes == {"grade": {"old": "good", "new": "good"}}
