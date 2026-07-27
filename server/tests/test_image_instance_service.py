import datetime

import pytest

from eyened_orm import (
    Creator,
    DeviceInstance,
    DeviceModel,
    ImageInstance,
    ImageInstanceTagLink,
    Patient,
    Project,
    Series,
    Study,
    Tag,
)
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.image_instance_repository import ImageInstanceRepository
from eyened_orm.repositories.tag_repository import TagRepository
from eyened_orm.tag import TagType

from server.services.acting_user import ActingUser
from server.services.exceptions import BadRequestError, NotFoundError
from server.services.image_instance_service import ImageInstanceService


class FakeAudit:
    """Records .record() calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


def _make_image(session, public_id: str) -> int:
    """Build the minimal graph an ImageInstance FK-requires; return its id."""
    project = Project(ProjectName=f"P-{public_id}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"ID-{public_id}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=datetime.date(2020, 1, 1))
    session.add(study)
    session.flush()
    series = Series(StudyID=study.StudyID)
    session.add(series)
    session.flush()
    model = DeviceModel(Manufacturer=f"Mf-{public_id}", ManufacturerModelName=f"M-{public_id}")
    session.add(model)
    session.flush()
    device = DeviceInstance(DeviceModelID=model.DeviceModelID, Description="d")
    session.add(device)
    session.flush()
    image = ImageInstance(
        PublicID=public_id,
        SeriesID=series.SeriesID,
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier=f"ds-{public_id}",
    )
    session.add(image)
    session.flush()
    return image.ImageInstanceID


def _make_link(
    session,
    tag: Tag,
    image_instance_id: int,
    creator_id: int,
    comment: str | None = None,
) -> ImageInstanceTagLink:
    """Construct an ImageInstanceTagLink directly, bypassing the service under test.

    Used as setup for tests that assert on a *later* call's audit output, so
    the setup itself doesn't add an unrelated record to a shared FakeAudit.
    """
    link = ImageInstanceTagLink(
        TagID=tag.TagID,
        ImageInstanceID=image_instance_id,
        CreatorID=creator_id,
        Comment=comment,
    )
    session.add(link)
    session.flush()
    return link


def _service(session, audit=None) -> ImageInstanceService:
    return ImageInstanceService(
        ImageInstanceRepository(session), TagRepository(session), audit=audit
    )


_READ_KW = dict(
    with_segmentations=False,
    with_form_annotations=False,
    with_model_segmentations=False,
)


def _actor(session) -> ActingUser:
    creator = Creator(CreatorName="alice", IsHuman=True)
    session.add(creator)
    session.flush()
    return ActingUser(id=creator.CreatorID, username=creator.CreatorName)


def _make_tag(session, creator_id: int, tag_type: TagType = TagType.ImageInstance) -> Tag:
    tag = Tag(
        TagName=f"t-{tag_type.name}",
        TagDescription="d",
        TagType=tag_type,
        CreatorID=creator_id,
    )
    session.add(tag)
    session.flush()
    return tag


def test_get_instance_unknown_raises_not_found(session):
    """Getting a missing instance is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).get_instance(999_999, **_READ_KW)


def test_get_by_public_id_unknown_raises_not_found(session):
    """Resolving a missing PublicID is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).get_by_public_id("nope", **_READ_KW)


def test_get_for_storage_unknown_raises_not_found(session):
    """get_for_storage on a missing PublicID raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).get_for_storage("missing")


def test_tag_instance_creates_link(session):
    """tag_instance links a tag to an instance and returns the link."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)

    link = _service(session).tag_instance("pub-1", tag.TagID, "hi", actor)

    assert link.TagID == tag.TagID
    assert link.Comment == "hi"
    assert link.Tag.TagID == tag.TagID


def test_tag_instance_creates_link_without_comment(session):
    """tag_instance with comment=None creates a link with no comment set."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)

    link = _service(session).tag_instance("pub-1", tag.TagID, None, actor)

    assert link.Comment is None


def test_tag_instance_unknown_instance_raises_not_found(session):
    """tag_instance on a missing instance is translated to NotFoundError."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    with pytest.raises(NotFoundError):
        _service(session).tag_instance("nope", tag.TagID, None, actor)


def test_tag_instance_unknown_tag_raises_not_found(session):
    """tag_instance with an unknown tag id is translated to NotFoundError."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    with pytest.raises(NotFoundError):
        _service(session).tag_instance("pub-1", 999_999, None, actor)


def test_tag_instance_wrong_tag_type_raises_bad_request(session):
    """tag_instance with a non-ImageInstance tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id, tag_type=TagType.Segmentation)
    with pytest.raises(BadRequestError):
        _service(session).tag_instance("pub-1", tag.TagID, None, actor)


def test_tag_instance_existing_updates_comment(session):
    """A second tag_instance with a comment updates the existing link, not duplicates."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    service = _service(session)

    service.tag_instance("pub-1", tag.TagID, "first", actor)
    link = service.tag_instance("pub-1", tag.TagID, "second", actor)

    assert link.Comment == "second"


def test_tag_instance_logs_insert(session):
    """tag_instance emits one INSERT record carrying the link identity + comment."""
    actor = _actor(session)
    image_id = _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()

    _service(session, audit).tag_instance("pub-1", tag.TagID, "hi", actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "INSERT"
    assert rec["entity"] == "ImageInstanceTagLink"
    assert rec["actor"] is actor
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "image_instance_id": image_id,
        "comment": "hi",
    }


def test_tag_instance_update_logs_raw_string_public_id(session):
    """Comment re-tag UPDATE audit carries the link identity + Comment diff.

    Pre-refactor quirk preserved: this site's identity uses the raw public_id
    string, not the int ImageInstanceID (unlike patch_instance_tag's UPDATE,
    see test_patch_instance_tag_logs_update_as_diff).
    """
    actor = _actor(session)
    image_id = _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    _make_link(session, tag, image_id, actor.id, comment="first")
    audit = FakeAudit()

    _service(session, audit).tag_instance("pub-1", tag.TagID, "second", actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "ImageInstanceTagLink"
    # ImageInstanceTagLink's composite PK means entity_id is null; changes
    # must carry the (tag_id, image_instance_id) identity alongside the
    # comment diff, or the audit row is unidentifiable.
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "image_instance_id": "pub-1",
        "Comment": {"old": "first", "new": "second"},
    }


def test_patch_instance_tag_updates_comment(session):
    """patch_instance_tag overwrites the comment on an existing link."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    service = _service(session)
    service.tag_instance("pub-1", tag.TagID, "old", actor)

    link = service.patch_instance_tag("pub-1", tag.TagID, "new", actor)

    assert link.Comment == "new"


def test_patch_instance_tag_unknown_link_raises_not_found(session):
    """patch_instance_tag with no existing link raises NotFoundError (-> 404)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    with pytest.raises(NotFoundError):
        _service(session).patch_instance_tag("pub-1", tag.TagID, "x", actor)


def test_patch_instance_tag_wrong_tag_type_raises_bad_request(session):
    """patch_instance_tag with a non-ImageInstance tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id, tag_type=TagType.Segmentation)
    with pytest.raises(BadRequestError):
        _service(session).patch_instance_tag("pub-1", tag.TagID, "x", actor)


def test_patch_instance_tag_logs_update_as_diff(session):
    """patch_instance_tag's UPDATE carries the link identity + Comment diff.

    This site's identity uses the int ImageInstanceID (unlike tag_instance's
    UPDATE, see test_tag_instance_update_logs_raw_string_public_id).
    """
    actor = _actor(session)
    image_id = _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    _make_link(session, tag, image_id, actor.id, comment="old")
    audit = FakeAudit()

    _service(session, audit).patch_instance_tag("pub-1", tag.TagID, "new", actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "ImageInstanceTagLink"
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "image_instance_id": image_id,
        "Comment": {"old": "old", "new": "new"},
    }


def test_untag_instance_removes_link(session):
    """untag_instance deletes the link for that (instance, tag)."""
    actor = _actor(session)
    image_id = _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    service = _service(session)
    service.tag_instance("pub-1", tag.TagID, None, actor)

    service.untag_instance("pub-1", tag.TagID, actor)

    assert ImageInstanceRepository(session).get_tag_link(tag.TagID, image_id) is None


def test_untag_instance_absent_link_is_idempotent(session):
    """untag_instance with no link present is a no-op (no error)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)

    # Does not raise even though no link exists.
    _service(session).untag_instance("pub-1", tag.TagID, actor)


def test_untag_instance_logs_delete_when_audit_present(session):
    """Untagging emits one DELETE record carrying the removed link's data."""
    actor = _actor(session)
    image_id = _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    _make_link(session, tag, image_id, actor.id, comment="bye")
    audit = FakeAudit()

    _service(session, audit).untag_instance("pub-1", tag.TagID, actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "DELETE"
    assert rec["entity"] == "ImageInstanceTagLink"
    assert rec["actor"] is actor
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "image_instance_id": image_id,
        "comment": "bye",
        "creator_id": actor.id,
    }
