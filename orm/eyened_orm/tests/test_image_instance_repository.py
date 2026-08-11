import datetime

from eyened_orm import (
    DeviceInstance,
    DeviceModel,
    ImageInstance,
    Patient,
    Project,
    Series,
    Study,
)
from eyened_orm.authz.scoping import projects_of
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.image_instance_repository import ImageInstanceRepository
from eyened_orm.utils.factories import admin_scope


def _make_image(session, public_id: str) -> int:
    """Build the minimal Series/Device graph an ImageInstance FK-requires.

    Returns the new ImageInstanceID.
    """
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


def test_get_full_graph_by_public_id_resolves_graph_and_digit_fallback(session):
    """Resolve by PublicID (all eager-load branches on), else by numeric PK string."""
    image_id = _make_image(session, "pub-str")
    _make_image(session, "9999")  # a PublicID that is itself a digit string
    repo = ImageInstanceRepository(session, scope=admin_scope())
    # all flags True so the conditional selectinload branches are exercised
    kw = dict(
        with_segmentations=True,
        with_form_annotations=True,
        with_model_segmentations=True,
    )

    by_public = repo.get_full_graph_by_public_id("pub-str", **kw)
    assert by_public is not None and by_public.ImageInstanceID == image_id
    assert by_public.Series.Study.Patient.Project is not None  # base graph loaded

    # A numeric string that is not a PublicID falls back to session.get(int)
    by_pk = repo.get_full_graph_by_public_id(str(image_id), **kw)
    assert by_pk is not None and by_pk.ImageInstanceID == image_id

    assert repo.get_full_graph_by_public_id("no-such-id", **kw) is None


def test_project_ids_for_images_agrees_with_the_shared_resolver(session):
    """The batch gate and ``projects_of`` resolve an image the same way.

    Both derive from ``_PARENT_OF``; re-forking either into its own hand-written
    join chain is exactly the drift this disagreement would catch. The
    single-project assertion keeps that comparison from passing vacuously on two
    empty answers.
    """
    first_id = _make_image(session, "pub-batch-1")
    second_id = _make_image(session, "pub-batch-2")
    repo = ImageInstanceRepository(session, scope=admin_scope())

    shared = {
        image_id: projects_of(session, ImageInstance, image_id)
        for image_id in (first_id, second_id)
    }
    assert all(len(projects) == 1 for projects in shared.values())
    expected = {image_id: next(iter(p)) for image_id, p in shared.items()}
    assert repo.project_ids_for_images([first_id, second_id]) == expected

    # An id that resolves to no image stays absent -- the caller's 404 hinge.
    assert repo.project_ids_for_images([first_id, -1]) == {first_id: expected[first_id]}


def test_get_with_storage_by_public_id_found_and_missing(session):
    """get_with_storage_by_public_id resolves by PublicID, or None if absent."""
    image_id = _make_image(session, "pub-store")
    repo = ImageInstanceRepository(session, scope=admin_scope())

    item = repo.get_with_storage_by_public_id("pub-store")
    assert item is not None and item.ImageInstanceID == image_id

    assert repo.get_with_storage_by_public_id("missing") is None
