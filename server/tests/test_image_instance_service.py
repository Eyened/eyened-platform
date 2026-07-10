import datetime

import pytest

from eyened_orm import (
    Creator,
    DeviceInstance,
    DeviceModel,
    ImageInstance,
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


def _service(logger=None) -> ImageInstanceService:
    return ImageInstanceService(
        ImageInstanceRepository(), TagRepository(), logger=logger
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


def test_get_instance_returns_it(session):
    """get_instance returns the instance at the given id."""
    image_id = _make_image(session, "pub-1")
    session.commit()

    got = _service().get_instance(session, image_id, **_READ_KW)

    assert got.ImageInstanceID == image_id


def test_get_instance_unknown_raises_not_found(session):
    """Getting a missing instance is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_instance(session, 999_999, **_READ_KW)


def test_get_by_public_id_unknown_raises_not_found(session):
    """Resolving a missing PublicID is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_by_public_id(session, "nope", **_READ_KW)


def test_get_for_storage_unknown_raises_not_found(session):
    """get_for_storage on a missing PublicID raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_for_storage(session, "missing")


def test_tag_instance_creates_link(session):
    """tag_instance links a tag to an instance and returns the link."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()

    link = _service().tag_instance(session, "pub-1", tag.TagID, "hi", actor)

    assert link.TagID == tag.TagID
    assert link.Comment == "hi"
    assert link.Tag.TagID == tag.TagID


def test_tag_instance_unknown_instance_raises_not_found(session):
    """tag_instance on a missing instance is translated to NotFoundError."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    session.commit()
    with pytest.raises(NotFoundError):
        _service().tag_instance(session, "nope", tag.TagID, None, actor)


def test_tag_instance_unknown_tag_raises_not_found(session):
    """tag_instance with an unknown tag id is translated to NotFoundError."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    session.commit()
    with pytest.raises(NotFoundError):
        _service().tag_instance(session, "pub-1", 999_999, None, actor)


def test_tag_instance_wrong_tag_type_raises_bad_request(session):
    """tag_instance with a non-ImageInstance tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id, tag_type=TagType.Segmentation)
    session.commit()
    with pytest.raises(BadRequestError):
        _service().tag_instance(session, "pub-1", tag.TagID, None, actor)


def test_tag_instance_existing_updates_comment(session):
    """A second tag_instance with a comment updates the existing link, not duplicates."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()

    service.tag_instance(session, "pub-1", tag.TagID, "first", actor)
    link = service.tag_instance(session, "pub-1", tag.TagID, "second", actor)

    assert link.Comment == "second"


def test_tag_instance_logs_insert(session):
    """tag_instance emits one insert audit record for ImageInstanceTagLink."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()
    logger = FakeAuditLogger()

    _service(logger).tag_instance(session, "pub-1", tag.TagID, None, actor)

    assert len(logger.inserts) == 1
    assert logger.inserts[0]["entity"] == "ImageInstanceTagLink"


def test_patch_instance_tag_updates_comment(session):
    """patch_instance_tag overwrites the comment on an existing link."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()
    service.tag_instance(session, "pub-1", tag.TagID, "old", actor)

    link = service.patch_instance_tag(session, "pub-1", tag.TagID, "new", actor)

    assert link.Comment == "new"


def test_patch_instance_tag_unknown_link_raises_not_found(session):
    """patch_instance_tag with no existing link raises NotFoundError (-> 404)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()
    with pytest.raises(NotFoundError):
        _service().patch_instance_tag(session, "pub-1", tag.TagID, "x", actor)


def test_untag_instance_removes_link(session):
    """untag_instance deletes the link for that (instance, tag)."""
    actor = _actor(session)
    image_id = _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()
    service.tag_instance(session, "pub-1", tag.TagID, None, actor)

    service.untag_instance(session, "pub-1", tag.TagID, actor)

    assert ImageInstanceRepository().get_tag_link(session, tag.TagID, image_id) is None


def test_untag_instance_absent_link_is_idempotent(session):
    """untag_instance with no link present is a no-op (no error)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()

    # Does not raise even though no link exists.
    _service().untag_instance(session, "pub-1", tag.TagID, actor)


def test_tag_instance_update_logs_raw_string_public_id(session):
    """Tag update audit logs use raw-string public_id, not int ImageInstanceID."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    session.commit()
    logger = FakeAuditLogger()
    service = _service(logger)

    service.tag_instance(session, "pub-1", tag.TagID, "first", actor)
    service.tag_instance(session, "pub-1", tag.TagID, "second", actor)

    assert len(logger.updates) == 1
    assert logger.updates[0]["entity"] == "ImageInstanceTagLink"
    assert logger.updates[0]["fields"]["image_instance_id"] == "pub-1"


def test_patch_instance_tag_wrong_tag_type_raises_bad_request(session):
    """patch_instance_tag with a non-ImageInstance tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id, tag_type=TagType.Segmentation)
    session.commit()
    with pytest.raises(BadRequestError):
        _service().patch_instance_tag(session, "pub-1", tag.TagID, "x", actor)
