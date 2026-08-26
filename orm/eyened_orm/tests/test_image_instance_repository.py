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


def _burn_project_ids(session, count: int) -> None:
    """Consume ``count`` ProjectIDs on projects nothing else references.

    With one project per image, ProjectID and ImageInstanceID both count 1, 2
    and the two id spaces are indistinguishable: a resolver returning
    ``{project_id: image_id}`` -- the mapping inverted -- satisfies every
    assertion below. In production image ids dwarf project ids, so that
    inversion would make the caller's ``set(image_ids) - set(by_image)``
    non-empty and 404 every batch. Offsetting one space past the other is what
    makes the test able to see it; do not simplify these rows away.
    """
    for i in range(count):
        session.add(Project(ProjectName=f"P-spacer-{i}", External=ExternalEnum.N))
    session.flush()


def test_project_ids_for_images_agrees_with_the_shared_resolver(session):
    """The batch gate and ``projects_of`` resolve an image to the same project.

    Stated as what the assertions prove and no more: two resolvers agree on the
    mapping, over ids whose two spaces are disjoint (see ``_burn_project_ids``)
    so agreeing on an inverted mapping is not enough. It does *not* prove the
    repository reaches the shared ``_PARENT_OF`` route -- a re-fork into an
    equivalent hand-written join passes this untouched, and a broken route
    fails on the single-project assertion below rather than on the comparison.
    ``test_the_batch_gate_resolves_projects_through_the_shared_helper``
    (server/tests/test_import_enqueue_gate.py) is what pins the binding.
    """
    # Burn one project past the number of images this test creates, so the
    # project id space starts strictly past the largest image id -- see
    # _burn_project_ids. Derived from image_public_ids rather than hardcoded,
    # so adding a third image/project here keeps the two id spaces disjoint
    # instead of quietly landing them on the same number.
    image_public_ids = ("pub-batch-1", "pub-batch-2")
    _burn_project_ids(session, len(image_public_ids) + 1)
    first_id, second_id = (_make_image(session, pid) for pid in image_public_ids)
    repo = ImageInstanceRepository(session, scope=admin_scope())

    shared = {
        image_id: projects_of(session, ImageInstance, image_id)
        for image_id in (first_id, second_id)
    }
    assert all(len(projects) == 1 for projects in shared.values())
    expected = {image_id: next(iter(p)) for image_id, p in shared.items()}
    # The offset actually landed: without this, a later edit that drops the
    # spacer rows leaves the comparison blind again with nothing failing.
    assert set(expected).isdisjoint(expected.values())
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
