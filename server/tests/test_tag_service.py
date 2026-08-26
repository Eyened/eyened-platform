from datetime import date

import pytest

from eyened_orm import Creator, CreatorTagLink, Tag
from eyened_orm.tag import StudyTagLink, TagType
from eyened_orm.repositories.tag_repository import TagRepository
from eyened_orm.utils.factories import (
    admin_scope,
    make_patient,
    make_project,
    make_study,
)

from server.services.acting_user import ActingUser
from server.services.exceptions import ConflictError, NotFoundError
from server.services.tag_service import TagService


class FakeAudit:
    """Records .record() calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


def _actor(session) -> ActingUser:
    """An ActingUser backed by a real Creator row (Tag.CreatorID is a FK)."""
    creator = Creator(CreatorName="alice", IsHuman=True)
    session.add(creator)
    session.flush()
    return ActingUser(id=creator.CreatorID, username=creator.CreatorName)


def _make_tag(
    session, creator_id: int, name: str = "T1", tag_type: TagType = TagType.Study
) -> Tag:
    tag = Tag(
        TagName=name, TagType=tag_type, TagDescription="", CreatorID=creator_id
    )
    session.add(tag)
    session.flush()
    return tag


def _service(session, actor: ActingUser, *, audit=None) -> TagService:
    scope = admin_scope(actor_id=actor.id, username=actor.username)
    return TagService(
        TagRepository(session, scope=scope),
        scope=scope,
        audit=audit,
    )


def test_create_tag_persists_and_returns(session):
    """Creating a tag stores it with the acting user as owner."""
    actor = _actor(session)

    tag = _service(session, actor).create_tag("New", "desc", TagType.Study)

    assert tag.TagName == "New"
    assert tag.TagType == TagType.Study
    assert tag.TagDescription == "desc"
    assert tag.CreatorID == actor.id


def test_create_tag_logs_insert(session):
    """Creating a tag emits one INSERT audit record naming the entity and actor."""
    actor = _actor(session)
    audit = FakeAudit()

    _service(session, actor, audit=audit).create_tag("New", "desc", TagType.Study)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "INSERT"
    assert audit.records[0]["entity"] == "Tag"
    assert audit.records[0]["actor"] == actor


def test_update_tag_changes_fields(session):
    """update_tag overwrites the provided fields in place."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id, "Old")

    updated = _service(session, actor).update_tag(tag.TagID, "New", "newdesc", None)

    assert updated.TagName == "New"
    assert updated.TagDescription == "newdesc"


def test_update_tag_unknown_raises_not_found(session):
    """Updating a missing tag is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service(session, actor).update_tag(999_999, "x", None, None)


def test_update_tag_logs_update_as_diff(session):
    """Updating a tag emits an UPDATE record whose changes are the diff-shaped {old, new}."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id, "Old")
    audit = FakeAudit()

    _service(session, actor, audit=audit).update_tag(tag.TagID, "New", None, None)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "UPDATE"
    assert audit.records[0]["entity"] == "Tag"
    assert audit.records[0]["changes"] == {"TagName": {"old": "Old", "new": "New"}}


def test_delete_tag_removes_it(session):
    """Deleting a tag removes it from the database."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)

    _service(session, actor).delete_tag(tag.TagID)

    assert TagRepository(session, scope=admin_scope()).get_by_id(tag.TagID) is None


def test_delete_tag_unknown_raises_not_found(session):
    """Deleting a missing tag is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service(session, actor).delete_tag(999_999)


def test_delete_tag_logs_delete(session):
    """Deleting a tag emits one DELETE audit record."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()

    _service(session, actor, audit=audit).delete_tag(tag.TagID)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "DELETE"
    assert audit.records[0]["entity"] == "Tag"


def test_star_tag_creates_link(session):
    """Starring a tag creates the CreatorTagLink for the acting user."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)

    _service(session, actor).star_tag(tag.TagID)

    assert TagRepository(session, scope=admin_scope()).get_star_link(tag.TagID, actor.id) is not None


def test_star_tag_is_idempotent(session):
    """Starring an already-starred tag adds no second link and logs nothing new."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()
    service = _service(session, actor, audit=audit)
    service.star_tag(tag.TagID)

    service.star_tag(tag.TagID)

    assert len(audit.records) == 1  # only the first star logged


def test_star_tag_unknown_raises_not_found(session):
    """Starring a missing tag is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service(session, actor).star_tag(999_999)


def test_star_tag_logs_insert(session):
    """Starring a tag emits one INSERT audit record for the link entity."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()

    _service(session, actor, audit=audit).star_tag(tag.TagID)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "INSERT"
    assert audit.records[0]["entity"] == "CreatorTagLink"


def test_unstar_tag_removes_link(session):
    """Unstarring removes the acting user's CreatorTagLink."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    _service(session, actor).star_tag(tag.TagID)

    _service(session, actor).unstar_tag(tag.TagID)

    assert TagRepository(session, scope=admin_scope()).get_star_link(tag.TagID, actor.id) is None


def test_unstar_tag_absent_is_noop(session):
    """Unstarring a tag that was never starred is a no-op (no error, no log)."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()

    _service(session, actor, audit=audit).unstar_tag(tag.TagID)

    assert len(audit.records) == 0


def test_unstar_tag_logs_delete(session):
    """Unstarring a starred tag emits one DELETE audit record for the link entity."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    _service(session, actor).star_tag(tag.TagID)
    audit = FakeAudit()

    _service(session, actor, audit=audit).unstar_tag(tag.TagID)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "DELETE"
    assert audit.records[0]["entity"] == "CreatorTagLink"


def test_delete_tag_in_use_raises_conflict(session):
    """A tag still applied to a study is refused with ConflictError (-> 409)."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    project = make_project(session, "P1")
    patient = make_patient(session, project, "pat-1")
    study = make_study(session, patient, date(2020, 1, 1))
    session.add(
        StudyTagLink(TagID=tag.TagID, StudyID=study.StudyID, CreatorID=actor.id)
    )
    session.flush()

    with pytest.raises(ConflictError) as excinfo:
        _service(session, actor).delete_tag(tag.TagID)

    assert excinfo.value.detail["code"] == "TAG_IN_USE"
    # _make_tag names it "T1"; the message must name the tag so the UI can say
    # which one. Read the literal, not tag.TagName -- the failed flush left the
    # Session needing a rollback.
    assert "T1" in excinfo.value.detail["message"]
    session.rollback()


def test_delete_tag_in_use_emits_no_audit_record(session):
    """A refused delete records nothing -- the audit trail must not claim a
    deletion that the database rejected."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    project = make_project(session, "P1")
    patient = make_patient(session, project, "pat-1")
    study = make_study(session, patient, date(2020, 1, 1))
    session.add(
        StudyTagLink(TagID=tag.TagID, StudyID=study.StudyID, CreatorID=actor.id)
    )
    session.flush()
    audit = FakeAudit()

    with pytest.raises(ConflictError):
        _service(session, actor, audit=audit).delete_tag(tag.TagID)

    assert audit.records == []
    session.rollback()


def test_delete_starred_tag_succeeds(session):
    """A star does not block a delete (CreatorTag still cascades)."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    session.add(CreatorTagLink(TagID=tag.TagID, CreatorID=actor.id))
    session.flush()

    _service(session, actor).delete_tag(tag.TagID)

    assert TagRepository(session, scope=admin_scope()).get_by_id(tag.TagID) is None
