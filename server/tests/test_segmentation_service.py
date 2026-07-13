import numpy as np
import pytest

from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.segmentation_repository import (
    ModelSegmentationRepository,
    SegmentationRepository,
)
from eyened_orm.repositories.tag_repository import TagRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import BadRequestError, NotFoundError
from server.services.segmentation_service import (
    ModelSegmentationService,
    SegmentationService,
)

from eyened_orm.tests.test_segmentation_repository import _make_segmentation


class FakeSegmentationDataStore:
    """In-memory stand-in for the zarr store (hand-rolled, per the codebase's
    FakeClient/FakeResponse pattern). Records writes; mimics the real store's
    None-on-empty read and ZarrArrayIndex assignment."""

    def __init__(self) -> None:
        self.data: dict[int, np.ndarray] = {}
        self._next_index = 0

    def write(self, segmentation, data, *, axis=None, slice_index=None) -> int:
        index = self._next_index
        self._next_index += 1
        segmentation.ZarrArrayIndex = index
        self.data[id(segmentation)] = data
        return index

    def read(self, segmentation, *, axis=None, slice_index=None):
        if segmentation.ZarrArrayIndex is None:
            return None
        return self.data.get(id(segmentation))


def _service(store: FakeSegmentationDataStore | None = None) -> SegmentationService:
    return SegmentationService(
        SegmentationRepository(),
        ImageInstanceRepository(),
        TagRepository(),
        store or FakeSegmentationDataStore(),
    )


def _model_service(
    store: FakeSegmentationDataStore | None = None,
) -> ModelSegmentationService:
    return ModelSegmentationService(
        ModelSegmentationRepository(), store or FakeSegmentationDataStore()
    )


def _actor(session, key: str = "actor") -> ActingUser:
    from eyened_orm import Creator

    creator = Creator(CreatorName=f"u-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    return ActingUser(id=creator.CreatorID, username=creator.CreatorName)


def test_get_segmentation_returns_row(session):
    """get_segmentation returns the row (tag links loaded)."""
    seg = _make_segmentation(session, "g1")
    session.commit()

    got = _service().get_segmentation(session, seg.SegmentationID)

    assert got.SegmentationID == seg.SegmentationID


def test_get_segmentation_unknown_raises_not_found(session):
    """get_segmentation on a missing id raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_segmentation(session, 999_999)


def test_read_data_unknown_raises_not_found(session):
    """read_data on a missing id raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().read_data(session, 999_999)


def test_read_data_empty_returns_none(session):
    """read_data on a row with no stored array returns None (no storage hit)."""
    seg = _make_segmentation(session, "r1")  # ZarrArrayIndex is None
    session.commit()

    assert _service().read_data(session, seg.SegmentationID) is None


def test_model_read_data_unknown_raises_not_found(session):
    """ModelSegmentationService.read_data on a missing id raises NotFoundError."""
    with pytest.raises(NotFoundError):
        _model_service().read_data(session, 999_999)
