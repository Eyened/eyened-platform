import datetime

import pytest

from eyened_orm import Creator, Patient, Project, Study, StudyTagLink, Tag
from eyened_orm.project import ExternalEnum
from eyened_orm.tag import TagType
from eyened_orm.repositories.study_repository import StudyRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import BadRequestError, NotFoundError
from server.services.study_service import StudyService
from eyened_orm.utils.factories import admin_scope


def _make_study(session) -> Study:
    project = Project(ProjectName="P", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier="ID1", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=datetime.date(2020, 1, 1))
    session.add(study)
    session.flush()
    return study


def _make_creator(session) -> Creator:
    creator = Creator(CreatorName="tester", IsHuman=True)
    session.add(creator)
    session.flush()
    return creator


def _make_tag(session, creator_id: int, tag_type: TagType = TagType.Study) -> Tag:
    tag = Tag(
        TagName=f"Tag-{tag_type.value}",
        TagType=tag_type,
        TagDescription="",
        CreatorID=creator_id,
    )
    session.add(tag)
    session.flush()
    return tag


def _make_link(
    session, tag: Tag, study: Study, creator_id: int, comment: str | None = None
) -> StudyTagLink:
    """Construct a StudyTagLink directly, bypassing the service under test.

    Used as setup for tests that assert on a *later* call's audit output, so
    the setup itself doesn't add an unrelated record to a shared FakeAudit.
    """
    link = StudyTagLink(
        TagID=tag.TagID, StudyID=study.StudyID, CreatorID=creator_id, Comment=comment
    )
    session.add(link)
    session.flush()
    return link


class FakeAudit:
    """Records .record() calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


def _actor() -> ActingUser:
    return ActingUser(id=1, username="alice")


def _service(session, actor: ActingUser | None = None, audit=None) -> StudyService:
    actor = actor if actor is not None else _actor()
    scope = admin_scope(actor_id=actor.id, username=actor.username)
    return StudyService(
        StudyRepository(session, scope=scope),
        scope=scope,
        audit=audit,
    )


def test_tag_study_creates_a_new_link(session):
    """First-time tagging inserts a StudyTagLink carrying the comment and actor id."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)

    link = _service(session).tag_study(study.StudyID, tag.TagID, "hi")

    assert link.TagID == tag.TagID
    assert link.StudyID == study.StudyID
    assert link.Comment == "hi"
    assert link.CreatorID == 1


def test_tag_study_unknown_study_raises_not_found(session):
    """Tagging a non-existent study is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).tag_study(999_999, 1, None)


def test_tag_study_unknown_tag_raises_not_found(session):
    """A valid study but unknown tag id is translated to NotFoundError (-> 404)."""
    study = _make_study(session)
    with pytest.raises(NotFoundError):
        _service(session).tag_study(study.StudyID, 999_999, None)


def test_tag_study_wrong_tag_type_raises_bad_request(session):
    """A non-Study tag is rejected with BadRequestError (-> 400), not linked."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID, tag_type=TagType.ImageInstance)

    with pytest.raises(BadRequestError):
        _service(session).tag_study(study.StudyID, tag.TagID, None)


def test_tag_study_existing_link_updates_comment(session):
    """Re-tagging an already-linked pair updates the comment in place (idempotent)."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    service = _service(session)
    service.tag_study(study.StudyID, tag.TagID, "first")

    link = service.tag_study(study.StudyID, tag.TagID, "second")

    assert link.Comment == "second"
    # Still a single link (no duplicate row created).
    assert StudyRepository(session, scope=admin_scope()).get_link(tag.TagID, study.StudyID) is not None


def test_tag_study_logs_insert_when_audit_present(session):
    """When audit is injected, creating a link emits one INSERT record."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    audit = FakeAudit()
    actor = _actor()

    _service(session, actor, audit).tag_study(study.StudyID, tag.TagID, "hi")

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "INSERT"
    assert rec["entity"] == "StudyTagLink"
    assert rec["actor"] == actor
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "study_id": study.StudyID,
        "comment": "hi",
    }


def test_untag_study_removes_the_link(session):
    """Untagging deletes the existing StudyTagLink for the (study, tag) pair."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    service = _service(session)
    service.tag_study(study.StudyID, tag.TagID, None)

    service.untag_study(study.StudyID, tag.TagID)

    assert StudyRepository(session, scope=admin_scope()).get_link(tag.TagID, study.StudyID) is None


def test_untag_study_unknown_study_raises_not_found(session):
    """Untagging a non-existent study is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).untag_study(999_999, 1)


def test_untag_study_no_link_is_idempotent(session):
    """Untagging a study that has no such link is a silent no-op, not an error."""
    study = _make_study(session)
    # No link exists; deleting is a no-op, not an error.
    _service(session).untag_study(study.StudyID, 999_999)

    # The no-op leaves no link behind (and did not raise).
    assert StudyRepository(session, scope=admin_scope()).get_link(999_999, study.StudyID) is None


def test_patch_study_tag_updates_comment(session):
    """Patching an existing link overwrites its comment with the new value."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    service = _service(session)
    service.tag_study(study.StudyID, tag.TagID, "old")

    link = service.patch_study_tag(study.StudyID, tag.TagID, "new")

    assert link.Comment == "new"


def test_patch_study_tag_missing_link_raises_not_found(session):
    """Patching when study+tag exist but no link does raises NotFoundError (-> 404)."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)

    with pytest.raises(NotFoundError):
        _service(session).patch_study_tag(study.StudyID, tag.TagID, "x")


def test_patch_study_tag_wrong_tag_type_raises_bad_request(session):
    """Patching a link via a non-Study tag is rejected with BadRequestError (-> 400)."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID, tag_type=TagType.Segmentation)

    with pytest.raises(BadRequestError):
        _service(session).patch_study_tag(study.StudyID, tag.TagID, "x")


def test_patch_study_tag_logs_update_as_diff(session):
    """Patching an existing link emits an UPDATE record whose changes are the diff shape."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    actor = _actor()
    _make_link(session, tag, study, actor.id, comment="old")
    audit = FakeAudit()

    _service(session, actor, audit).patch_study_tag(study.StudyID, tag.TagID, "new")

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "StudyTagLink"
    assert rec["actor"] == actor
    # StudyTagLink's composite PK means entity_id is null; changes must carry
    # the (tag_id, study_id) identity alongside the comment diff, or the
    # audit row is unidentifiable.
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "study_id": study.StudyID,
        "Comment": {"old": "old", "new": "new"},
    }


def test_untag_study_logs_delete_when_audit_present(session):
    """Untagging emits one DELETE record carrying the removed link's data."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    actor = _actor()
    _make_link(session, tag, study, actor.id, comment="bye")
    audit = FakeAudit()

    _service(session, actor, audit).untag_study(study.StudyID, tag.TagID)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "DELETE"
    assert rec["entity"] == "StudyTagLink"
    assert rec["actor"] == actor
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "study_id": study.StudyID,
        "comment": "bye",
        "creator_id": actor.id,
    }
