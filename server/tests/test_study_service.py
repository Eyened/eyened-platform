import datetime

import pytest

from eyened_orm import Creator, Patient, Project, Study, StudyTagLink, Tag
from eyened_orm.project import ExternalEnum
from eyened_orm.tag import TagType
from eyened_orm.repositories.study_repository import StudyRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import BadRequestError, NotFoundError
from server.services.study_service import StudyService


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


def _service(logger=None) -> StudyService:
    return StudyService(StudyRepository(), logger=logger)


def _actor() -> ActingUser:
    return ActingUser(id=1, username="alice")


def test_tag_study_creates_a_new_link(session):
    """First-time tagging inserts a StudyTagLink carrying the comment and actor id."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)

    link = _service().tag_study(session, study.StudyID, tag.TagID, "hi", _actor())

    assert link.TagID == tag.TagID
    assert link.StudyID == study.StudyID
    assert link.Comment == "hi"
    assert link.CreatorID == 1


def test_tag_study_unknown_study_raises_not_found(session):
    """Tagging a non-existent study is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().tag_study(session, 999_999, 1, None, _actor())


def test_tag_study_unknown_tag_raises_not_found(session):
    """A valid study but unknown tag id is translated to NotFoundError (-> 404)."""
    study = _make_study(session)
    with pytest.raises(NotFoundError):
        _service().tag_study(session, study.StudyID, 999_999, None, _actor())


def test_tag_study_wrong_tag_type_raises_bad_request(session):
    """A non-Study tag is rejected with BadRequestError (-> 400), not linked."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID, tag_type=TagType.ImageInstance)

    with pytest.raises(BadRequestError):
        _service().tag_study(session, study.StudyID, tag.TagID, None, _actor())


def test_tag_study_existing_link_updates_comment(session):
    """Re-tagging an already-linked pair updates the comment in place (idempotent)."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    service = _service()
    service.tag_study(session, study.StudyID, tag.TagID, "first", _actor())

    link = service.tag_study(session, study.StudyID, tag.TagID, "second", _actor())

    assert link.Comment == "second"
    # Still a single link (no duplicate row created).
    assert StudyRepository().get_link(session, tag.TagID, study.StudyID) is not None


def test_tag_study_logs_insert_when_logger_present(session):
    """When a logger is injected, creating a link emits one insert audit record."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    logger = FakeAuditLogger()

    _service(logger).tag_study(session, study.StudyID, tag.TagID, "hi", _actor())

    assert len(logger.inserts) == 1
    ins = logger.inserts[0]
    assert ins["user"] == "alice"
    assert ins["entity"] == "StudyTagLink"
    assert ins["endpoint"] == f"POST /api/studies/{study.StudyID}/tags"
    assert ins["fields"] == {"tag_id": tag.TagID, "study_id": study.StudyID, "comment": "hi"}


def test_untag_study_removes_the_link(session):
    """Untagging deletes the existing StudyTagLink for the (study, tag) pair."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    service = _service()
    service.tag_study(session, study.StudyID, tag.TagID, None, _actor())

    service.untag_study(session, study.StudyID, tag.TagID, _actor())

    assert StudyRepository().get_link(session, tag.TagID, study.StudyID) is None


def test_untag_study_unknown_study_raises_not_found(session):
    """Untagging a non-existent study is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().untag_study(session, 999_999, 1, _actor())


def test_untag_study_no_link_is_idempotent(session):
    """Untagging a study that has no such link is a silent no-op, not an error."""
    study = _make_study(session)
    # No link exists; deleting is a no-op, not an error.
    _service().untag_study(session, study.StudyID, 999_999, _actor())


def test_patch_study_tag_updates_comment(session):
    """Patching an existing link overwrites its comment with the new value."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    service = _service()
    service.tag_study(session, study.StudyID, tag.TagID, "old", _actor())

    link = service.patch_study_tag(session, study.StudyID, tag.TagID, "new", _actor())

    assert link.Comment == "new"


def test_patch_study_tag_missing_link_raises_not_found(session):
    """Patching when study+tag exist but no link does raises NotFoundError (-> 404)."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)

    with pytest.raises(NotFoundError):
        _service().patch_study_tag(session, study.StudyID, tag.TagID, "x", _actor())


def test_patch_study_tag_wrong_tag_type_raises_bad_request(session):
    """Patching a link via a non-Study tag is rejected with BadRequestError (-> 400)."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID, tag_type=TagType.Segmentation)

    with pytest.raises(BadRequestError):
        _service().patch_study_tag(session, study.StudyID, tag.TagID, "x", _actor())


def test_patch_study_tag_logs_update_when_logger_present(session):
    """Patching an existing link emits one update audit record with the comment diff."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    logger = FakeAuditLogger()
    service = _service(logger)
    service.tag_study(session, study.StudyID, tag.TagID, "old", _actor())

    service.patch_study_tag(session, study.StudyID, tag.TagID, "new", _actor())

    assert len(logger.updates) == 1
    upd = logger.updates[0]
    assert upd["user"] == "alice"
    assert upd["entity"] == "StudyTagLink"
    assert upd["endpoint"] == f"PATCH /api/studies/{study.StudyID}/tags/{tag.TagID}"
    assert upd["fields"] == {"tag_id": tag.TagID, "study_id": study.StudyID}
    assert upd["changes"] == {"comment": "old -> new"}


def test_untag_study_logs_delete_when_logger_present(session):
    """Untagging emits one delete audit record carrying the removed link's data."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID)
    logger = FakeAuditLogger()
    service = _service(logger)
    service.tag_study(session, study.StudyID, tag.TagID, "bye", _actor())

    service.untag_study(session, study.StudyID, tag.TagID, _actor())

    assert len(logger.deletes) == 1
    dele = logger.deletes[0]
    assert dele["user"] == "alice"
    assert dele["entity"] == "StudyTagLink"
    assert dele["endpoint"] == f"DELETE /api/studies/{study.StudyID}/tags/{tag.TagID}"
    assert dele["fields"] == {"tag_id": tag.TagID, "study_id": study.StudyID}
    assert dele["deleted_data"] == {
        "tag_id": tag.TagID,
        "study_id": study.StudyID,
        "comment": "bye",
        "creator_id": 1,
    }
