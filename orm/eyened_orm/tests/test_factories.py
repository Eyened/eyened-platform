from sqlalchemy import func, select

from eyened_orm import ImageInstance
from eyened_orm.utils.factories import seed_search_dataset


def test_seed_search_dataset_builds_the_documented_graph(session):
    """The fixed dataset seeds 4 instances across 2 projects, one of them inactive."""
    data = seed_search_dataset(session)

    assert set(data.images) == {"a1", "a2", "b1", "inactive"}
    assert set(data.projects) == {"alpha", "beta"}
    assert data.images["inactive"].Inactive is True
    assert session.scalar(select(func.count()).select_from(ImageInstance)) == 4


def test_seeded_images_are_renderable_by_the_dto_converter(session):
    """Every active instance has the primary storage DTOConverter requires."""
    data = seed_search_dataset(session)

    for key in ("a1", "a2", "b1"):
        assert data.images[key].primary_storage is not None


def test_make_image_in_project_anchors_through_the_patient(session):
    """The image resolves to its project four joins up -- the schema's only anchor."""
    from eyened_orm import ImageInstance, Patient, Series, Study
    from eyened_orm.utils.factories import make_image_in_project, make_project
    from sqlalchemy import select

    project = make_project(session, "P-anchor")
    image = make_image_in_project(session, project, "img-1")

    resolved = session.scalar(
        select(Patient.ProjectID)
        .select_from(ImageInstance)
        .join(Series, Series.SeriesID == ImageInstance.SeriesID)
        .join(Study, Study.StudyID == Series.StudyID)
        .join(Patient, Patient.PatientID == Study.PatientID)
        .where(ImageInstance.ImageInstanceID == image.ImageInstanceID)
    )
    assert resolved == project.ProjectID


def test_make_image_in_project_twice_does_not_collide(session):
    """Two calls in one project must not collide on PatientIdentifier or backend key."""
    from eyened_orm.utils.factories import make_image_in_project, make_project

    project = make_project(session, "P-twice")
    a = make_image_in_project(session, project, "img-a")
    b = make_image_in_project(session, project, "img-b")

    assert a.ImageInstanceID != b.ImageInstanceID
