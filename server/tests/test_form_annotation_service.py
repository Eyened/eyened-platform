import pytest

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
)
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.form_annotation_repository import (
    FormAnnotationRepository,
)
from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.tag_repository import TagRepository

from server.services.exceptions import NotFoundError
from server.services.form_annotation_service import FormAnnotationService


def _service() -> FormAnnotationService:
    return FormAnnotationService(
        FormAnnotationRepository(),
        ImageInstanceRepository(),
        TagRepository(),
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
    study = Study(PatientID=patient.PatientID)
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
