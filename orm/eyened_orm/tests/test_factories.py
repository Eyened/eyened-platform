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
