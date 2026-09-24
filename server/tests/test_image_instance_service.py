import datetime
from types import SimpleNamespace

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
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.utils.factories import admin_scope, scope_for


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


def _service(
    session, actor: ActingUser | None = None, *, audit=None
) -> ImageInstanceService:
    scope = (
        admin_scope(actor_id=actor.id, username=actor.username)
        if actor is not None
        else admin_scope()
    )
    return ImageInstanceService(
        ImageInstanceRepository(session, scope=scope),
        TagRepository(session, scope=scope),
        scope=scope,
        audit=audit,
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

    link = _service(session, actor).tag_instance("pub-1", tag.TagID, "hi")

    assert link.TagID == tag.TagID
    assert link.Comment == "hi"
    assert link.Tag.TagID == tag.TagID


def test_tag_instance_creates_link_without_comment(session):
    """tag_instance with comment=None creates a link with no comment set."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)

    link = _service(session, actor).tag_instance("pub-1", tag.TagID, None)

    assert link.Comment is None


def test_tag_instance_unknown_instance_raises_not_found(session):
    """tag_instance on a missing instance is translated to NotFoundError."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    with pytest.raises(NotFoundError):
        _service(session, actor).tag_instance("nope", tag.TagID, None)


def test_tag_instance_unknown_tag_raises_not_found(session):
    """tag_instance with an unknown tag id is translated to NotFoundError."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    with pytest.raises(NotFoundError):
        _service(session, actor).tag_instance("pub-1", 999_999, None)


def test_tag_instance_wrong_tag_type_raises_bad_request(session):
    """tag_instance with a non-ImageInstance tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id, tag_type=TagType.Segmentation)
    with pytest.raises(BadRequestError):
        _service(session, actor).tag_instance("pub-1", tag.TagID, None)


def test_tag_instance_existing_updates_comment(session):
    """A second tag_instance with a comment updates the existing link, not duplicates."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    service = _service(session, actor)

    service.tag_instance("pub-1", tag.TagID, "first")
    link = service.tag_instance("pub-1", tag.TagID, "second")

    assert link.Comment == "second"


def test_tag_instance_logs_insert(session):
    """tag_instance emits one INSERT record carrying the link identity + comment."""
    actor = _actor(session)
    image_id = _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()

    _service(session, actor, audit=audit).tag_instance("pub-1", tag.TagID, "hi")

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "INSERT"
    assert rec["entity"] == "ImageInstanceTagLink"
    assert rec["actor"] == actor
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

    _service(session, actor, audit=audit).tag_instance("pub-1", tag.TagID, "second")

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
    service = _service(session, actor)
    service.tag_instance("pub-1", tag.TagID, "old")

    link = service.patch_instance_tag("pub-1", tag.TagID, "new")

    assert link.Comment == "new"


def test_patch_instance_tag_unknown_link_raises_not_found(session):
    """patch_instance_tag with no existing link raises NotFoundError (-> 404)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    with pytest.raises(NotFoundError):
        _service(session, actor).patch_instance_tag("pub-1", tag.TagID, "x")


def test_patch_instance_tag_wrong_tag_type_raises_bad_request(session):
    """patch_instance_tag with a non-ImageInstance tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id, tag_type=TagType.Segmentation)
    with pytest.raises(BadRequestError):
        _service(session, actor).patch_instance_tag("pub-1", tag.TagID, "x")


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

    _service(session, actor, audit=audit).patch_instance_tag("pub-1", tag.TagID, "new")

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
    service = _service(session, actor)
    service.tag_instance("pub-1", tag.TagID, None)

    service.untag_instance("pub-1", tag.TagID)

    assert ImageInstanceRepository(session, scope=admin_scope()).get_tag_link(tag.TagID, image_id) is None


def test_untag_instance_absent_link_is_idempotent(session):
    """untag_instance with no link present is a no-op (no error)."""
    actor = _actor(session)
    _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)

    # Does not raise even though no link exists.
    _service(session, actor).untag_instance("pub-1", tag.TagID)


def test_untag_instance_logs_delete_when_audit_present(session):
    """Untagging emits one DELETE record carrying the removed link's data."""
    actor = _actor(session)
    image_id = _make_image(session, "pub-1")
    tag = _make_tag(session, actor.id)
    _make_link(session, tag, image_id, actor.id, comment="bye")
    audit = FakeAudit()

    _service(session, actor, audit=audit).untag_instance("pub-1", tag.TagID)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "DELETE"
    assert rec["entity"] == "ImageInstanceTagLink"
    assert rec["actor"] == actor
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "image_instance_id": image_id,
        "comment": "bye",
        "creator_id": actor.id,
    }


def _cross_anchored_annotation(session):
    """Seed the mis-scoped shape: image in project A, annotation anchored in B.

    ``FormAnnotation``'s project anchor is its ``PatientID``
    (``_PARENT_OF[FormAnnotation]``), a different anchor from the image's, so a
    row whose ``PatientID`` sits in project B and whose ``ImageInstanceID`` sits
    in project A belongs to B while hanging off an A image. That disagreement
    is what makes the eager-loaded collection worth a scope of its own: the
    scoped root passes on A, and the row rides along.

    Ids are read out *before* ``commit()`` and the session is emptied after it,
    so the read under test issues real SELECTs instead of being served the
    relationship from the identity map -- which would pass whatever the loader
    options say.
    """
    from eyened_orm.utils.factories import (
        make_creator,
        make_device,
        make_form_annotation,
        make_form_schema,
        make_image,
        make_patient,
        make_project,
        make_series,
        make_storage_backend,
        make_study,
    )

    backend = make_storage_backend(session)
    device = make_device(session, "cross")
    project_a = make_project(session, "cross-A")
    patient_a = make_patient(session, project_a, "pat-cross-A")
    study_a = make_study(session, patient_a, datetime.date(2024, 1, 1))
    series_a = make_series(session, study_a)
    image_a = make_image(session, series_a, device, backend, "img-cross-A")

    project_b = make_project(session, "cross-B")
    patient_b = make_patient(session, project_b, "pat-cross-B")
    schema = make_form_schema(session, "cross-schema")
    author = make_creator(session, "cross-author")
    annotation = make_form_annotation(session, schema, patient_b, author, image=image_a)
    annotation.FormData = {"PHI": "project-B-only-diagnosis"}
    session.flush()

    ids = SimpleNamespace(
        project_a=project_a.ProjectID,
        image=image_a.ImageInstanceID,
        public_id=image_a.PublicID,
        annotation=annotation.FormAnnotationID,
    )
    session.commit()
    session.expunge_all()
    return ids


def _scoped_service(session, scope) -> ImageInstanceService:
    return ImageInstanceService(
        ImageInstanceRepository(session, scope=scope),
        TagRepository(session, scope=scope),
        scope=scope,
    )


_WITH_ANNOTATIONS = dict(
    with_segmentations=False,
    with_form_annotations=True,
    with_model_segmentations=False,
)


def test_eager_loaded_form_annotations_are_scoped_to_the_caller(session):
    """A member of A only never receives an annotation anchored in project B."""
    ids = _cross_anchored_annotation(session)
    scope = scope_for(ids.project_a, role=ProjectRole.read_only)

    item = _scoped_service(session, scope).get_instance(ids.image, **_WITH_ANNOTATIONS)

    assert [a.FormAnnotationID for a in item.FormAnnotations] == []


def test_eager_loaded_form_annotations_are_scoped_on_the_public_id_read_too(session):
    """The PublicID reader shares the loader options, so it shares the filter."""
    ids = _cross_anchored_annotation(session)
    scope = scope_for(ids.project_a, role=ProjectRole.read_only)

    item = _scoped_service(session, scope).get_by_public_id(
        ids.public_id, **_WITH_ANNOTATIONS
    )

    assert [a.FormAnnotationID for a in item.FormAnnotations] == []


def test_an_admin_still_receives_the_eager_loaded_form_annotation(session):
    """The filter must narrow a member's read, not everyone's: admins see all."""
    ids = _cross_anchored_annotation(session)

    item = _service(session).get_instance(ids.image, **_WITH_ANNOTATIONS)

    assert [a.FormAnnotationID for a in item.FormAnnotations] == [ids.annotation]


def test_an_in_project_annotation_still_loads_for_a_member(session):
    """The scoped loader must not empty the collection wholesale.

    Without this the two assertions above are satisfied by a loader that
    returns nothing at all, which is not the fix and would silently break the
    endpoint.
    """
    from eyened_orm.utils.factories import (
        make_creator,
        make_form_annotation,
        make_form_schema,
        make_patient,
    )
    from eyened_orm import Project

    ids = _cross_anchored_annotation(session)
    project_a = session.get(Project, ids.project_a)
    patient_a = make_patient(session, project_a, "pat-cross-A2")
    schema = make_form_schema(session, "in-project-schema")
    author = make_creator(session, "in-project-author")
    image = session.get(ImageInstance, ids.image)
    in_project = make_form_annotation(
        session, schema, patient_a, author, image=image
    )
    in_project_id = in_project.FormAnnotationID
    session.commit()
    session.expunge_all()

    scope = scope_for(ids.project_a, role=ProjectRole.read_only)
    item = _scoped_service(session, scope).get_instance(ids.image, **_WITH_ANNOTATIONS)

    assert [a.FormAnnotationID for a in item.FormAnnotations] == [in_project_id]


def test_a_nested_annotation_still_names_the_image_it_hangs_off(session):
    """The nested DTO's ``image_id`` survives the load, and is not resolved.

    ``form_annotation_to_get`` names an image only off a relationship that is
    already loaded -- it resolves none from the Session, on purpose -- so this
    reader has to load ``FormAnnotation.ImageInstance`` or every annotation
    nested in an image response comes back with ``image_id: null``. That is the
    fail-closed direction rather than a leak, which is exactly why a green
    suite would not otherwise say a word about it.

    The id asserted is the root image's own PublicID: this collection cannot
    contain an annotation pointing anywhere else.
    """
    from eyened_orm.utils.factories import (
        make_creator,
        make_form_annotation,
        make_form_schema,
        make_patient,
    )
    from eyened_orm import Project
    from server.dtos.dto_converter import DTOConverter

    ids = _cross_anchored_annotation(session)
    patient_a = make_patient(session, session.get(Project, ids.project_a), "pat-nest")
    make_form_annotation(
        session,
        make_form_schema(session, "nest-schema"),
        patient_a,
        make_creator(session, "nest-author"),
        image=session.get(ImageInstance, ids.image),
    )
    session.commit()
    session.expunge_all()

    scope = scope_for(ids.project_a, role=ProjectRole.read_only)
    item = _scoped_service(session, scope).get_instance(ids.image, **_WITH_ANNOTATIONS)
    dto = DTOConverter.image_instance_to_get(item, with_form_annotations=True)

    assert [a.image_id for a in dto.form_annotations] == [ids.public_id]
