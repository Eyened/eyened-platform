import pytest

from eyened_orm import Creator, Tag
from eyened_orm.tag import TagType
from eyened_orm.repositories.tag_repository import TagRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import NotFoundError
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


def _service(session, audit=None) -> TagService:
    return TagService(TagRepository(session), audit=audit)


def test_create_tag_persists_and_returns(session):
    """Creating a tag stores it with the acting user as owner."""
    actor = _actor(session)

    tag = _service(session).create_tag("New", "desc", TagType.Study, actor)

    assert tag.TagName == "New"
    assert tag.TagType == TagType.Study
    assert tag.TagDescription == "desc"
    assert tag.CreatorID == actor.id


def test_create_tag_logs_insert(session):
    """Creating a tag emits one INSERT audit record naming the entity and actor."""
    actor = _actor(session)
    audit = FakeAudit()

    _service(session, audit).create_tag("New", "desc", TagType.Study, actor)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "INSERT"
    assert audit.records[0]["entity"] == "Tag"
    assert audit.records[0]["actor"] is actor


def test_update_tag_changes_fields(session):
    """update_tag overwrites the provided fields in place."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id, "Old")

    updated = _service(session).update_tag(tag.TagID, "New", "newdesc", None, actor)

    assert updated.TagName == "New"
    assert updated.TagDescription == "newdesc"


def test_update_tag_unknown_raises_not_found(session):
    """Updating a missing tag is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service(session).update_tag(999_999, "x", None, None, actor)


def test_update_tag_logs_update_as_diff(session):
    """Updating a tag emits an UPDATE record whose changes are the diff-shaped {old, new}."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id, "Old")
    audit = FakeAudit()

    _service(session, audit).update_tag(tag.TagID, "New", None, None, actor)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "UPDATE"
    assert audit.records[0]["entity"] == "Tag"
    assert audit.records[0]["changes"] == {"TagName": {"old": "Old", "new": "New"}}


def test_delete_tag_removes_it(session):
    """Deleting a tag removes it from the database."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)

    _service(session).delete_tag(tag.TagID, actor)

    assert TagRepository(session).get_by_id(tag.TagID) is None


def test_delete_tag_unknown_raises_not_found(session):
    """Deleting a missing tag is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service(session).delete_tag(999_999, actor)


def test_delete_tag_logs_delete(session):
    """Deleting a tag emits one DELETE audit record."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()

    _service(session, audit).delete_tag(tag.TagID, actor)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "DELETE"
    assert audit.records[0]["entity"] == "Tag"


def test_star_tag_creates_link(session):
    """Starring a tag creates the CreatorTagLink for the acting user."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)

    _service(session).star_tag(tag.TagID, actor)

    assert TagRepository(session).get_star_link(tag.TagID, actor.id) is not None


def test_star_tag_is_idempotent(session):
    """Starring an already-starred tag adds no second link and logs nothing new."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()
    service = _service(session, audit)
    service.star_tag(tag.TagID, actor)

    service.star_tag(tag.TagID, actor)

    assert len(audit.records) == 1  # only the first star logged


def test_star_tag_unknown_raises_not_found(session):
    """Starring a missing tag is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service(session).star_tag(999_999, actor)


def test_star_tag_logs_insert(session):
    """Starring a tag emits one INSERT audit record for the link entity."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()

    _service(session, audit).star_tag(tag.TagID, actor)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "INSERT"
    assert audit.records[0]["entity"] == "CreatorTagLink"


def test_unstar_tag_removes_link(session):
    """Unstarring removes the acting user's CreatorTagLink."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    _service(session).star_tag(tag.TagID, actor)

    _service(session).unstar_tag(tag.TagID, actor)

    assert TagRepository(session).get_star_link(tag.TagID, actor.id) is None


def test_unstar_tag_absent_is_noop(session):
    """Unstarring a tag that was never starred is a no-op (no error, no log)."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()

    _service(session, audit).unstar_tag(tag.TagID, actor)

    assert len(audit.records) == 0


def test_unstar_tag_logs_delete(session):
    """Unstarring a starred tag emits one DELETE audit record for the link entity."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    _service(session).star_tag(tag.TagID, actor)
    audit = FakeAudit()

    _service(session, audit).unstar_tag(tag.TagID, actor)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "DELETE"
    assert audit.records[0]["entity"] == "CreatorTagLink"
