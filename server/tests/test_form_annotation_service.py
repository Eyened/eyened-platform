import pytest
from datetime import date

from eyened_orm import (
    Creator,
    DeviceInstance,
    DeviceModel,
    FormAnnotation,
    FormSchema,
    ImageInstance,
    Patient,
    Project,
    Series,
    Study,
    Tag,
)
from eyened_orm.project import ExternalEnum
from eyened_orm.tag import TagType
from eyened_orm.repositories.form_annotation_repository import (
    FormAnnotationRepository,
)
from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.tag_repository import TagRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import BadRequestError, NotFoundError
from server.services.form_annotation_service import FormAnnotationService


class FakeAudit:
    """Records .record() calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


def _service(session, audit=None) -> FormAnnotationService:
    return FormAnnotationService(
        FormAnnotationRepository(session),
        ImageInstanceRepository(session),
        TagRepository(session),
        audit=audit,
    )


def _make_patient_and_schema(session, key: str) -> tuple[int, int]:
    """Create a Project/Patient + FormSchema; return (patient_id, schema_id)."""
    project = Project(ProjectName=f"P-{key}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"ID-{key}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    schema = FormSchema(SchemaName=f"S-{key}")
    session.add(schema)
    session.flush()
    return patient.PatientID, schema.FormSchemaID


def _make_annotation(session, key: str, *, inactive: bool = False) -> FormAnnotation:
    """Create a minimal active/inactive FormAnnotation; return the row."""
    patient_id, schema_id = _make_patient_and_schema(session, key)
    creator = Creator(CreatorName=f"c-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    ann = FormAnnotation(
        FormSchemaID=schema_id,
        PatientID=patient_id,
        CreatorID=creator.CreatorID,
        Inactive=inactive,
        FormData={"answer": 1},
    )
    session.add(ann)
    session.flush()
    return ann


def _make_image(session, public_id: str) -> int:
    """Build the minimal graph an ImageInstance FK-requires; return its id."""
    project = Project(ProjectName=f"IP-{public_id}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"IID-{public_id}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=date.today())
    session.add(study)
    session.flush()
    series = Series(StudyID=study.StudyID)
    session.add(series)
    session.flush()
    model = DeviceModel(Manufacturer="Mf", ManufacturerModelName="M")
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


def _actor(session, key: str = "actor") -> ActingUser:
    creator = Creator(CreatorName=f"u-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    return ActingUser(id=creator.CreatorID, username=creator.CreatorName)


def _make_tag(session, creator_id: int, tag_type: TagType = TagType.FormAnnotation) -> Tag:
    tag = Tag(
        TagName=f"t-{tag_type.name}-{creator_id}",
        TagDescription="d",
        TagType=tag_type,
        CreatorID=creator_id,
    )
    session.add(tag)
    session.flush()
    return tag


def test_list_annotations_excludes_inactive(session):
    """list_annotations returns only active rows (no image_id filter)."""
    keep = _make_annotation(session, "keep")
    _make_annotation(session, "gone", inactive=True)

    rows = _service(session).list_annotations(
        patient_id=None,
        study_id=None,
        image_id=None,
        form_schema_id=None,
        sub_task_id=None,
    )

    ids = {r.FormAnnotationID for r in rows}
    assert keep.FormAnnotationID in ids
    assert all(not r.Inactive for r in rows)


def test_list_annotations_unknown_image_id_raises_not_found(session):
    """An image_id filter that resolves to nothing raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).list_annotations(
            patient_id=None,
            study_id=None,
            image_id="no-such-image",
            form_schema_id=None,
            sub_task_id=None,
        )


def test_get_annotation_unknown_raises_not_found(session):
    """Getting a missing annotation is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).get_annotation(999_999)


def test_get_value_unknown_raises_not_found(session):
    """get_value on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).get_value(999_999)


def test_create_resolves_image_and_persists(session):
    """create resolves image_id and persists the row."""
    actor = _actor(session)
    patient_id, schema_id = _make_patient_and_schema(session, "c1")
    image_id = _make_image(session, "img-1")

    ann = _service(session).create(
        form_schema_id=schema_id,
        patient_id=patient_id,
        study_id=None,
        image_id="img-1",
        laterality=None,
        sub_task_id=None,
        form_data={"a": 1},
        form_annotation_reference_id=None,
        actor=actor,
    )

    assert ann.FormAnnotationID is not None
    assert ann.ImageInstanceID == image_id


def test_create_unknown_image_raises_not_found(session):
    """create with an unresolvable image_id raises NotFoundError (-> 404)."""
    actor = _actor(session)
    patient_id, schema_id = _make_patient_and_schema(session, "c2")
    with pytest.raises(NotFoundError):
        _service(session).create(
            form_schema_id=schema_id,
            patient_id=patient_id,
            study_id=None,
            image_id="no-image",
            laterality=None,
            sub_task_id=None,
            form_data=None,
            form_annotation_reference_id=None,
            actor=actor,
        )


def test_create_logs_insert(session):
    """Creating an annotation emits one INSERT audit record naming the entity."""
    actor = _actor(session)
    patient_id, schema_id = _make_patient_and_schema(session, "ci1")
    audit = FakeAudit()

    ann = _service(session, audit).create(
        form_schema_id=schema_id,
        patient_id=patient_id,
        study_id=None,
        image_id=None,
        laterality=None,
        sub_task_id=None,
        form_data={"a": 1},
        form_annotation_reference_id=None,
        actor=actor,
    )

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "INSERT"
    assert rec["entity"] == "FormAnnotation"
    assert rec["entity_id"] == ann.FormAnnotationID


def test_update_applies_field(session):
    """update applies a provided field to the annotation."""
    actor = _actor(session)
    ann = _make_annotation(session, "u1")

    updated = _service(session).update(
        ann.FormAnnotationID, {"form_data": {"b": 2}}, actor
    )

    assert updated.FormData == {"b": 2}


def test_update_unknown_raises_not_found(session):
    """update on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).update(999_999, {"form_data": {}}, _actor(session))


def test_update_logs_diff_with_applied_columns(session):
    """update's UPDATE audit carries a true {old, new} diff keyed by the
    PascalCase column actually set (FormData) — the sanctioned removal of the
    pre-refactor 'None -> <new>' quirk (Decision #3: the old snake_case
    getattr never matched the PascalCase column, so every entry read
    'None -> <new>' regardless of the real old value)."""
    actor = _actor(session)
    ann = _make_annotation(session, "ud1")
    audit = FakeAudit()

    _service(session, audit).update(
        ann.FormAnnotationID, {"form_data": {"b": 2}}, actor
    )

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "FormAnnotation"
    assert rec["entity_id"] == ann.FormAnnotationID
    assert rec["changes"] == {"FormData": {"old": {"answer": 1}, "new": {"b": 2}}}


def test_update_image_id_diffs_on_image_instance_id_column(session):
    """An image_id update diffs the ImageInstanceID column it actually set
    (via the same snake->Pascal map used to setattr), not the snake_case
    'image_id' request key — the other half of the Decision-3 removal."""
    actor = _actor(session)
    ann = _make_annotation(session, "ud2")
    image_id = _make_image(session, "img-2")
    audit = FakeAudit()

    _service(session, audit).update(
        ann.FormAnnotationID, {"image_id": "img-2"}, actor
    )

    assert audit.records[0]["changes"] == {
        "ImageInstanceID": {"old": None, "new": image_id}
    }


def test_soft_delete_sets_inactive(session):
    """soft_delete flags the row Inactive."""
    actor = _actor(session)
    ann = _make_annotation(session, "d1")

    _service(session).soft_delete(ann.FormAnnotationID, actor)

    assert ann.Inactive is True


def test_soft_delete_unknown_raises_not_found(session):
    """soft_delete on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).soft_delete(999_999, _actor(session))


def test_soft_delete_logs_delete(session):
    """soft_delete's DELETE audit carries a snapshot of the annotation's fields."""
    actor = _actor(session)
    ann = _make_annotation(session, "sd1")
    audit = FakeAudit()

    _service(session, audit).soft_delete(ann.FormAnnotationID, actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "DELETE"
    assert rec["entity"] == "FormAnnotation"
    assert rec["entity_id"] == ann.FormAnnotationID
    assert rec["changes"]["patient_id"] == ann.PatientID


def test_set_value_overwrites_form_data(session):
    """set_value overwrites the annotation's FormData payload."""
    actor = _actor(session)
    ann = _make_annotation(session, "v1")

    _service(session).set_value(ann.FormAnnotationID, {"new": 9}, actor)

    assert ann.FormData == {"new": 9}


def test_set_value_unknown_raises_not_found(session):
    """set_value on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).set_value(999_999, {}, _actor(session))


def test_set_value_logs_update_without_changes(session):
    """set_value's UPDATE audit carries no changes payload — pre-refactor
    log_simple never included field detail for this high-frequency op;
    preserved as-is (not a Decision-3-style improvement site)."""
    actor = _actor(session)
    ann = _make_annotation(session, "sv1")
    audit = FakeAudit()

    _service(session, audit).set_value(ann.FormAnnotationID, {"x": 1}, actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "FormAnnotation"
    assert rec["entity_id"] == ann.FormAnnotationID
    assert rec.get("changes") is None


def test_tag_creates_link(session):
    """tag links a FormAnnotation tag and returns the link."""
    actor = _actor(session)
    ann = _make_annotation(session, "t1")
    tag = _make_tag(session, actor.id)

    link = _service(session).tag(ann.FormAnnotationID, tag.TagID, "hi", actor)

    assert link.TagID == tag.TagID
    assert link.Comment == "hi"
    assert link.Tag.TagID == tag.TagID


def test_tag_unknown_annotation_raises_not_found(session):
    """tag on a missing annotation is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    with pytest.raises(NotFoundError):
        _service(session).tag(999_999, tag.TagID, None, actor)


def test_tag_unknown_tag_raises_not_found(session):
    """tag with an unknown tag id is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t2")
    with pytest.raises(NotFoundError):
        _service(session).tag(ann.FormAnnotationID, 999_999, None, actor)


def test_tag_wrong_type_raises_bad_request(session):
    """tag with a non-FormAnnotation tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t3")
    tag = _make_tag(session, actor.id, tag_type=TagType.ImageInstance)
    with pytest.raises(BadRequestError):
        _service(session).tag(ann.FormAnnotationID, tag.TagID, None, actor)


def test_tag_existing_updates_comment(session):
    """A second tag with a comment updates the existing link, not duplicates."""
    actor = _actor(session)
    ann = _make_annotation(session, "t4")
    tag = _make_tag(session, actor.id)
    service = _service(session)

    service.tag(ann.FormAnnotationID, tag.TagID, "first", actor)
    link = service.tag(ann.FormAnnotationID, tag.TagID, "second", actor)

    assert link.Comment == "second"


def test_tag_logs_insert(session):
    """tag's INSERT audit carries the link identity + comment."""
    actor = _actor(session)
    ann = _make_annotation(session, "ti1")
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()

    _service(session, audit).tag(ann.FormAnnotationID, tag.TagID, "hi", actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "INSERT"
    assert rec["entity"] == "FormAnnotationTagLink"
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "form_annotation_id": ann.FormAnnotationID,
        "comment": "hi",
    }


def test_tag_update_logs_diff_with_identity(session):
    """A re-tag comment UPDATE (via tag()) folds the (tag_id,
    form_annotation_id) identity into changes alongside the Comment diff.
    FormAnnotationTagLink has a composite PK, so entity_id is null; identity
    must live in changes (matches the INSERT above and untag's DELETE below)
    or the audit row is unidentifiable."""
    actor = _actor(session)
    ann = _make_annotation(session, "ti2")
    tag = _make_tag(session, actor.id)
    _service(session).tag(ann.FormAnnotationID, tag.TagID, "first", actor)
    audit = FakeAudit()

    _service(session, audit).tag(ann.FormAnnotationID, tag.TagID, "second", actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "FormAnnotationTagLink"
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "form_annotation_id": ann.FormAnnotationID,
        "Comment": {"old": "first", "new": "second"},
    }


def test_patch_tag_updates_comment(session):
    """patch_tag overwrites the comment on an existing link."""
    actor = _actor(session)
    ann = _make_annotation(session, "t5")
    tag = _make_tag(session, actor.id)
    service = _service(session)
    service.tag(ann.FormAnnotationID, tag.TagID, "old", actor)

    link = service.patch_tag(ann.FormAnnotationID, tag.TagID, "new", actor)

    assert link.Comment == "new"


def test_patch_tag_unknown_link_raises_not_found(session):
    """patch_tag with no existing link raises NotFoundError (-> 404)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t6")
    tag = _make_tag(session, actor.id)
    with pytest.raises(NotFoundError):
        _service(session).patch_tag(ann.FormAnnotationID, tag.TagID, "x", actor)


def test_patch_tag_logs_update_as_diff(session):
    """patch_tag's UPDATE folds the same (tag_id, form_annotation_id) identity
    into changes alongside the Comment diff. Separate code path from tag()'s
    re-tag branch above — must be verified independently."""
    actor = _actor(session)
    ann = _make_annotation(session, "pt1")
    tag = _make_tag(session, actor.id)
    _service(session).tag(ann.FormAnnotationID, tag.TagID, "old", actor)
    audit = FakeAudit()

    _service(session, audit).patch_tag(ann.FormAnnotationID, tag.TagID, "new", actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "FormAnnotationTagLink"
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "form_annotation_id": ann.FormAnnotationID,
        "Comment": {"old": "old", "new": "new"},
    }


def test_untag_removes_link(session):
    """untag deletes the link for that (annotation, tag)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t7")
    tag = _make_tag(session, actor.id)
    service = _service(session)
    service.tag(ann.FormAnnotationID, tag.TagID, None, actor)

    service.untag(ann.FormAnnotationID, tag.TagID, actor)

    assert (
        FormAnnotationRepository(session).get_tag_link(
            tag.TagID, ann.FormAnnotationID
        )
        is None
    )


def test_untag_absent_link_is_idempotent(session):
    """untag with no link present is a no-op (no error)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t8")
    tag = _make_tag(session, actor.id)

    # Does not raise even though no link exists.
    _service(session).untag(ann.FormAnnotationID, tag.TagID, actor)


def test_untag_logs_delete(session):
    """untag's DELETE audit carries the removed link's identity + data."""
    actor = _actor(session)
    ann = _make_annotation(session, "ut1")
    tag = _make_tag(session, actor.id)
    _service(session).tag(ann.FormAnnotationID, tag.TagID, "bye", actor)
    audit = FakeAudit()

    _service(session, audit).untag(ann.FormAnnotationID, tag.TagID, actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "DELETE"
    assert rec["entity"] == "FormAnnotationTagLink"
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "form_annotation_id": ann.FormAnnotationID,
        "comment": "bye",
        "creator_id": actor.id,
    }
