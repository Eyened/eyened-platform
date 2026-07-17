import pytest

from eyened_orm import Creator, Tag
from eyened_orm.tag import TagType
from eyened_orm.repositories.tag_repository import TagRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import NotFoundError
from server.services.tag_service import TagService


class FakeAuditLogger:
    """Records logging calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.inserts: list[dict] = []
        self.updates: list[dict] = []
        self.deletes: list[dict] = []

    def log_insert(self, **kwargs) -> None:
        self.inserts.append(kwargs)

    def log_update(self, **kwargs) -> None:
        self.updates.append(kwargs)

    def log_delete(self, **kwargs) -> None:
        self.deletes.append(kwargs)


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


def _service(logger=None) -> TagService:
    return TagService(TagRepository(), logger=logger)


def test_create_tag_persists_and_returns(session):
    """Creating a tag stores it with the acting user as owner."""
    actor = _actor(session)

    tag = _service().create_tag(session, "New", "desc", TagType.Study, actor)

    assert tag.TagName == "New"
    assert tag.TagType == TagType.Study
    assert tag.TagDescription == "desc"
    assert tag.CreatorID == actor.id


def test_create_tag_logs_insert(session):
    """Creating a tag emits one insert audit record naming the entity and user."""
    actor = _actor(session)
    logger = FakeAuditLogger()

    _service(logger).create_tag(session, "New", "desc", TagType.Study, actor)

    assert len(logger.inserts) == 1
    assert logger.inserts[0]["entity"] == "Tag"
    assert logger.inserts[0]["user"] == actor.username


def test_update_tag_changes_fields(session):
    """update_tag overwrites the provided fields in place."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id, "Old")

    updated = _service().update_tag(
        session, tag.TagID, "New", "newdesc", None, actor
    )

    assert updated.TagName == "New"
    assert updated.TagDescription == "newdesc"


def test_update_tag_unknown_raises_not_found(session):
    """Updating a missing tag is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service().update_tag(session, 999_999, "x", None, None, actor)


def test_update_tag_logs_update(session):
    """Updating a tag emits one update audit record."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id, "Old")
    logger = FakeAuditLogger()

    _service(logger).update_tag(session, tag.TagID, "New", None, None, actor)

    assert len(logger.updates) == 1
    assert logger.updates[0]["entity"] == "Tag"


def test_delete_tag_removes_it(session):
    """Deleting a tag removes it from the database."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)

    _service().delete_tag(session, tag.TagID, actor)

    assert TagRepository().get_by_id(session, tag.TagID) is None


def test_delete_tag_unknown_raises_not_found(session):
    """Deleting a missing tag is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service().delete_tag(session, 999_999, actor)


def test_delete_tag_logs_delete(session):
    """Deleting a tag emits one delete audit record."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    logger = FakeAuditLogger()

    _service(logger).delete_tag(session, tag.TagID, actor)

    assert len(logger.deletes) == 1
    assert logger.deletes[0]["entity"] == "Tag"


def test_star_tag_creates_link(session):
    """Starring a tag creates the CreatorTagLink for the acting user."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)

    _service().star_tag(session, tag.TagID, actor)

    assert (
        TagRepository().get_star_link(session, tag.TagID, actor.id) is not None
    )


def test_star_tag_is_idempotent(session):
    """Starring an already-starred tag adds no second link and logs nothing new."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    logger = FakeAuditLogger()
    service = _service(logger)
    service.star_tag(session, tag.TagID, actor)

    service.star_tag(session, tag.TagID, actor)

    assert len(logger.inserts) == 1  # only the first star logged


def test_star_tag_unknown_raises_not_found(session):
    """Starring a missing tag is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    with pytest.raises(NotFoundError):
        _service().star_tag(session, 999_999, actor)


def test_star_tag_logs_insert(session):
    """Starring a tag emits one insert audit record for the link entity."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    logger = FakeAuditLogger()

    _service(logger).star_tag(session, tag.TagID, actor)

    assert len(logger.inserts) == 1
    assert logger.inserts[0]["entity"] == "CreatorTagLink"


def test_unstar_tag_removes_link(session):
    """Unstarring removes the acting user's CreatorTagLink."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    _service().star_tag(session, tag.TagID, actor)

    _service().unstar_tag(session, tag.TagID, actor)

    assert TagRepository().get_star_link(session, tag.TagID, actor.id) is None


def test_unstar_tag_absent_is_noop(session):
    """Unstarring a tag that was never starred is a no-op (no error, no log)."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    logger = FakeAuditLogger()

    _service(logger).unstar_tag(session, tag.TagID, actor)

    assert len(logger.deletes) == 0


def test_unstar_tag_logs_delete(session):
    """Unstarring a starred tag emits one delete audit record for the link entity."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    _service().star_tag(session, tag.TagID, actor)
    logger = FakeAuditLogger()

    _service(logger).unstar_tag(session, tag.TagID, actor)

    assert len(logger.deletes) == 1
    assert logger.deletes[0]["entity"] == "CreatorTagLink"
