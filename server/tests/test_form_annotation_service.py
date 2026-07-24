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
from eyened_orm.task import TaskState
from eyened_orm.repositories.form_annotation_repository import (
    FormAnnotationRepository,
)
from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.tag_repository import TagRepository
from eyened_orm.repositories.task_repository import SubTaskRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import BadRequestError, NotFoundError
from server.services.form_annotation_service import FormAnnotationService


def _service() -> FormAnnotationService:
    return FormAnnotationService(
        FormAnnotationRepository(),
        ImageInstanceRepository(),
        TagRepository(),
        SubTaskRepository(),
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


def test_list_annotations_excludes_inactive(session):
    """list_annotations returns only active rows (no image_id filter)."""
    keep = _make_annotation(session, "keep")
    _make_annotation(session, "gone", inactive=True)
    session.commit()

    rows = _service().list_annotations(
        session,
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
        _service().list_annotations(
            session,
            patient_id=None,
            study_id=None,
            image_id="no-such-image",
            form_schema_id=None,
            sub_task_id=None,
        )


def test_get_annotation_unknown_raises_not_found(session):
    """Getting a missing annotation is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_annotation(session, 999_999)


def test_get_value_returns_form_data(session):
    """get_value returns the annotation's FormData payload."""
    ann = _make_annotation(session, "val")
    session.commit()

    assert _service().get_value(session, ann.FormAnnotationID) == {"answer": 1}


def test_get_value_unknown_raises_not_found(session):
    """get_value on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_value(session, 999_999)


def _actor(session, key: str = "actor") -> ActingUser:
    creator = Creator(CreatorName=f"u-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    return ActingUser(id=creator.CreatorID, username=creator.CreatorName)


def test_create_resolves_image_and_persists(session):
    """create resolves image_id and persists the row."""
    actor = _actor(session)
    patient_id, schema_id = _make_patient_and_schema(session, "c1")
    image_id = _make_image(session, "img-1")
    session.commit()

    ann = _service().create(
        session,
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


def _make_subtask(session, *, creator_id: int | None = None) -> "SubTask":
    from eyened_orm import SubTask, Task, TaskDefinition

    td = TaskDefinition(TaskDefinitionName="td")
    session.add(td)
    session.flush()
    task = Task(
        TaskName="T",
        TaskDefinitionID=td.TaskDefinitionID,
        CreatorID=creator_id,
        TaskState=TaskState.NotStarted,
    )
    session.add(task)
    session.flush()
    st = SubTask(TaskID=task.TaskID, CreatorID=creator_id)
    session.add(st)
    session.flush()
    return st


def test_create_with_subtask_claims_unassigned_subtask(session):
    """create with sub_task_id on an unassigned subtask claims it for the actor."""
    actor = _actor(session, "claim1")
    patient_id, schema_id = _make_patient_and_schema(session, "claim1")
    st = _make_subtask(session)
    session.commit()

    _service().create(
        session,
        form_schema_id=schema_id,
        patient_id=patient_id,
        study_id=None,
        image_id=None,
        laterality=None,
        sub_task_id=st.SubTaskID,
        form_data={"a": 1},
        form_annotation_reference_id=None,
        actor=actor,
    )

    session.refresh(st)
    assert st.CreatorID == actor.id


def test_create_with_subtask_already_assigned_unchanged(session):
    """create with sub_task_id on an already-assigned subtask leaves CreatorID unchanged."""
    other = _actor(session, "owner1")
    actor = _actor(session, "claim2")
    patient_id, schema_id = _make_patient_and_schema(session, "claim2")
    st = _make_subtask(session, creator_id=other.id)
    session.commit()

    _service().create(
        session,
        form_schema_id=schema_id,
        patient_id=patient_id,
        study_id=None,
        image_id=None,
        laterality=None,
        sub_task_id=st.SubTaskID,
        form_data={"a": 1},
        form_annotation_reference_id=None,
        actor=actor,
    )

    session.refresh(st)
    assert st.CreatorID == other.id


def test_create_unknown_image_raises_not_found(session):
    """create with an unresolvable image_id raises NotFoundError (-> 404)."""
    actor = _actor(session)
    patient_id, schema_id = _make_patient_and_schema(session, "c2")
    session.commit()
    with pytest.raises(NotFoundError):
        _service().create(
            session,
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


def test_update_applies_field(session):
    """update applies a provided field to the annotation."""
    actor = _actor(session)
    ann = _make_annotation(session, "u1")
    session.commit()

    updated = _service().update(
        session, ann.FormAnnotationID, {"form_data": {"b": 2}}, actor
    )

    assert updated.FormData == {"b": 2}


def test_update_unknown_raises_not_found(session):
    """update on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().update(session, 999_999, {"form_data": {}}, _actor(session))


def test_soft_delete_sets_inactive(session):
    """soft_delete flags the row Inactive."""
    actor = _actor(session)
    ann = _make_annotation(session, "d1")
    session.commit()

    _service().soft_delete(session, ann.FormAnnotationID, actor)

    assert ann.Inactive is True


def test_soft_delete_unknown_raises_not_found(session):
    """soft_delete on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().soft_delete(session, 999_999, _actor(session))


def test_set_value_overwrites_form_data(session):
    """set_value overwrites the annotation's FormData payload."""
    actor = _actor(session)
    ann = _make_annotation(session, "v1")
    session.commit()

    _service().set_value(session, ann.FormAnnotationID, {"new": 9}, actor)

    assert ann.FormData == {"new": 9}


def test_set_value_unknown_raises_not_found(session):
    """set_value on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().set_value(session, 999_999, {}, _actor(session))


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


def test_tag_creates_link(session):
    """tag links a FormAnnotation tag and returns the link."""
    actor = _actor(session)
    ann = _make_annotation(session, "t1")
    tag = _make_tag(session, actor.id)
    session.commit()

    link = _service().tag(
        session, ann.FormAnnotationID, tag.TagID, "hi", actor
    )

    assert link.TagID == tag.TagID
    assert link.Comment == "hi"
    assert link.Tag.TagID == tag.TagID


def test_tag_unknown_annotation_raises_not_found(session):
    """tag on a missing annotation is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    session.commit()
    with pytest.raises(NotFoundError):
        _service().tag(session, 999_999, tag.TagID, None, actor)


def test_tag_unknown_tag_raises_not_found(session):
    """tag with an unknown tag id is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t2")
    session.commit()
    with pytest.raises(NotFoundError):
        _service().tag(session, ann.FormAnnotationID, 999_999, None, actor)


def test_tag_wrong_type_raises_bad_request(session):
    """tag with a non-FormAnnotation tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t3")
    tag = _make_tag(session, actor.id, tag_type=TagType.ImageInstance)
    session.commit()
    with pytest.raises(BadRequestError):
        _service().tag(session, ann.FormAnnotationID, tag.TagID, None, actor)


def test_tag_existing_updates_comment(session):
    """A second tag with a comment updates the existing link, not duplicates."""
    actor = _actor(session)
    ann = _make_annotation(session, "t4")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()

    service.tag(session, ann.FormAnnotationID, tag.TagID, "first", actor)
    link = service.tag(session, ann.FormAnnotationID, tag.TagID, "second", actor)

    assert link.Comment == "second"


def test_patch_tag_updates_comment(session):
    """patch_tag overwrites the comment on an existing link."""
    actor = _actor(session)
    ann = _make_annotation(session, "t5")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()
    service.tag(session, ann.FormAnnotationID, tag.TagID, "old", actor)

    link = service.patch_tag(session, ann.FormAnnotationID, tag.TagID, "new", actor)

    assert link.Comment == "new"


def test_patch_tag_unknown_link_raises_not_found(session):
    """patch_tag with no existing link raises NotFoundError (-> 404)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t6")
    tag = _make_tag(session, actor.id)
    session.commit()
    with pytest.raises(NotFoundError):
        _service().patch_tag(session, ann.FormAnnotationID, tag.TagID, "x", actor)


def test_untag_removes_link(session):
    """untag deletes the link for that (annotation, tag)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t7")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()
    service.tag(session, ann.FormAnnotationID, tag.TagID, None, actor)

    service.untag(session, ann.FormAnnotationID, tag.TagID, actor)

    assert (
        FormAnnotationRepository().get_tag_link(
            session, tag.TagID, ann.FormAnnotationID
        )
        is None
    )


def test_untag_absent_link_is_idempotent(session):
    """untag with no link present is a no-op (no error)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t8")
    tag = _make_tag(session, actor.id)
    session.commit()

    # Does not raise even though no link exists.
    _service().untag(session, ann.FormAnnotationID, tag.TagID, actor)
