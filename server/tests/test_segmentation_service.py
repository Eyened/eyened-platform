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
from eyened_orm.repositories.task_repository import SubTaskRepository

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
        subtask_repository=SubTaskRepository(),
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


from eyened_orm.segmentation import DataRepresentation, Datatype


def _image_public_id(session, key: str) -> str:
    """Create a standalone segmentation and return its image's PublicID."""
    seg = _make_segmentation(session, key)
    return seg.ImageInstance.PublicID


def test_create_persists_and_writes(session):
    """create builds the row, writes via the store, and persists it."""
    actor = _actor(session)
    seg = _make_segmentation(session, "c0")
    image_id = seg.ImageInstance.PublicID
    session.commit()
    store = FakeSegmentationDataStore()

    created = _service(store).create(
        session,
        image_id=image_id,
        feature_id=seg.FeatureID,
        subtask_id=None,
        data_type=Datatype.R8UI,
        data_representation=DataRepresentation.Binary,
        depth=1,
        height=4,
        width=4,
        sparse_axis=None,
        image_projection_matrix=None,
        scan_indices=None,
        threshold=None,
        reference_segmentation_id=None,
        array=np.zeros((1, 4, 4), dtype=np.uint8),
        actor=actor,
    )

    assert created.SegmentationID is not None
    assert created.ZarrArrayIndex == 0  # fake store assigned it


def test_create_empty_array_fills_zeros(session):
    """create with array=None fills a zeros volume from the image shape."""
    actor = _actor(session)
    seg = _make_segmentation(session, "c1")
    image_id = seg.ImageInstance.PublicID
    session.commit()

    created = _service().create(
        session,
        image_id=image_id,
        feature_id=seg.FeatureID,
        subtask_id=None,
        data_type=Datatype.R8UI,
        data_representation=DataRepresentation.Binary,
        depth=1,
        height=4,
        width=4,
        sparse_axis=None,
        image_projection_matrix=None,
        scan_indices=None,
        threshold=None,
        reference_segmentation_id=None,
        array=None,
        actor=actor,
    )

    assert created.shape == (1, 4, 4)


def _make_subtask(session, *, creator_id: int | None = None):
    from eyened_orm import SubTask, Task, TaskDefinition
    from eyened_orm.task import TaskState

    td = TaskDefinition(TaskDefinitionName="td-seg")
    session.add(td)
    session.flush()
    task = Task(
        TaskName="T-seg",
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
    """create with subtask_id on an unassigned subtask claims it for the actor."""
    actor = _actor(session, "claim1")
    seg = _make_segmentation(session, "sc0")
    image_id = seg.ImageInstance.PublicID
    st = _make_subtask(session)
    session.commit()

    _service().create(
        session,
        image_id=image_id,
        feature_id=seg.FeatureID,
        subtask_id=st.SubTaskID,
        data_type=Datatype.R8UI,
        data_representation=DataRepresentation.Binary,
        depth=1,
        height=4,
        width=4,
        sparse_axis=None,
        image_projection_matrix=None,
        scan_indices=None,
        threshold=None,
        reference_segmentation_id=None,
        array=np.zeros((1, 4, 4), dtype=np.uint8),
        actor=actor,
    )

    session.refresh(st)
    assert st.CreatorID == actor.id


def test_create_with_subtask_already_assigned_unchanged(session):
    """create with subtask_id on an already-assigned subtask leaves CreatorID unchanged."""
    other = _actor(session, "owner1")
    actor = _actor(session, "claim2")
    seg = _make_segmentation(session, "sc1")
    image_id = seg.ImageInstance.PublicID
    st = _make_subtask(session, creator_id=other.id)
    session.commit()

    _service().create(
        session,
        image_id=image_id,
        feature_id=seg.FeatureID,
        subtask_id=st.SubTaskID,
        data_type=Datatype.R8UI,
        data_representation=DataRepresentation.Binary,
        depth=1,
        height=4,
        width=4,
        sparse_axis=None,
        image_projection_matrix=None,
        scan_indices=None,
        threshold=None,
        reference_segmentation_id=None,
        array=np.zeros((1, 4, 4), dtype=np.uint8),
        actor=actor,
    )

    session.refresh(st)
    assert st.CreatorID == other.id


def test_create_unknown_image_raises_not_found(session):
    """create with an unresolvable image_id raises NotFoundError (-> 404)."""
    actor = _actor(session)
    seg = _make_segmentation(session, "c2")
    session.commit()
    with pytest.raises(NotFoundError):
        _service().create(
            session,
            image_id="no-such-image",
            feature_id=seg.FeatureID,
            subtask_id=None,
            data_type=Datatype.R8UI,
            data_representation=DataRepresentation.Binary,
            depth=1,
            height=4,
            width=4,
            sparse_axis=None,
            image_projection_matrix=None,
            scan_indices=None,
            threshold=None,
            reference_segmentation_id=None,
            array=None,
            actor=actor,
        )


def test_create_shape_mismatch_raises_bad_request(session):
    """create with an array whose shape != the segmentation raises BadRequest."""
    actor = _actor(session)
    seg = _make_segmentation(session, "c3")
    image_id = seg.ImageInstance.PublicID
    session.commit()
    with pytest.raises(BadRequestError):
        _service().create(
            session,
            image_id=image_id,
            feature_id=seg.FeatureID,
            subtask_id=None,
            data_type=Datatype.R8UI,
            data_representation=DataRepresentation.Binary,
            depth=1,
            height=4,
            width=4,
            sparse_axis=None,
            image_projection_matrix=None,
            scan_indices=None,
            threshold=None,
            reference_segmentation_id=None,
            array=np.zeros((2, 4, 4), dtype=np.uint8),  # depth 2 != 1
            actor=actor,
        )


def test_write_data_unknown_raises_not_found(session):
    """write_data on a missing id raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().write_data(
            session, 999_999, np.zeros((1, 4, 4), dtype=np.uint8), actor=_actor(session)
        )


def test_write_data_persists_zarr_index(session):
    """write_data stores via the port and persists the ZarrArrayIndex."""
    actor = _actor(session)
    seg = _make_segmentation(session, "w1")
    session.commit()
    store = FakeSegmentationDataStore()

    updated = _service(store).write_data(
        session, seg.SegmentationID, np.zeros((1, 4, 4), dtype=np.uint8), actor=actor
    )

    assert updated.ZarrArrayIndex == 0


def test_soft_delete_sets_inactive(session):
    """soft_delete flags the row Inactive."""
    actor = _actor(session)
    seg = _make_segmentation(session, "d1")
    session.commit()

    _service().soft_delete(session, seg.SegmentationID, actor)

    assert seg.Inactive is True


def test_soft_delete_unknown_raises_not_found(session):
    """soft_delete on a missing id raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().soft_delete(session, 999_999, _actor(session))


def test_patch_applies_threshold_and_feature(session):
    """patch updates threshold and feature_id on the row."""
    actor = _actor(session)
    seg = _make_segmentation(session, "p1")
    other = _make_segmentation(session, "p1-feat")
    session.commit()

    updated = _service().patch(
        session,
        seg.SegmentationID,
        reference_segmentation_id=None,
        feature_id=other.FeatureID,
        threshold=0.5,
        actor=actor,
    )

    assert updated.Threshold == 0.5
    assert updated.FeatureID == other.FeatureID


def test_patch_unknown_raises_not_found(session):
    """patch on a missing id raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().patch(
            session,
            999_999,
            reference_segmentation_id=None,
            feature_id=None,
            threshold=1.0,
            actor=_actor(session),
        )


from eyened_orm import Tag
from eyened_orm.tag import TagType


def _make_tag(
    session, creator_id: int, tag_type: TagType = TagType.Segmentation
) -> Tag:
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
    """tag links a Segmentation-type tag and returns the link."""
    actor = _actor(session)
    seg = _make_segmentation(session, "t1")
    tag = _make_tag(session, actor.id)
    session.commit()

    link = _service().tag(session, seg.SegmentationID, tag.TagID, actor)

    assert link.TagID == tag.TagID
    assert link.SegmentationID == seg.SegmentationID
    assert link.Tag.TagID == tag.TagID


def test_tag_unknown_segmentation_raises_not_found(session):
    """tag on a missing segmentation raises NotFoundError (-> 404)."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    session.commit()
    with pytest.raises(NotFoundError):
        _service().tag(session, 999_999, tag.TagID, actor)


def test_tag_unknown_tag_raises_not_found(session):
    """tag with an unknown tag id raises NotFoundError (-> 404)."""
    actor = _actor(session)
    seg = _make_segmentation(session, "t2")
    session.commit()
    with pytest.raises(NotFoundError):
        _service().tag(session, seg.SegmentationID, 999_999, actor)


def test_tag_wrong_type_raises_bad_request(session):
    """tag with a non-Segmentation tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    seg = _make_segmentation(session, "t3")
    tag = _make_tag(session, actor.id, tag_type=TagType.ImageInstance)
    session.commit()
    with pytest.raises(BadRequestError):
        _service().tag(session, seg.SegmentationID, tag.TagID, actor)


def test_tag_is_idempotent(session):
    """A second tag with the same (seg, tag) returns the existing link, no dup."""
    actor = _actor(session)
    seg = _make_segmentation(session, "t4")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()

    service.tag(session, seg.SegmentationID, tag.TagID, actor)
    link = service.tag(session, seg.SegmentationID, tag.TagID, actor)

    assert link.TagID == tag.TagID


def test_untag_removes_link(session):
    """untag deletes the link for that (segmentation, tag)."""
    actor = _actor(session)
    seg = _make_segmentation(session, "t5")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service()
    service.tag(session, seg.SegmentationID, tag.TagID, actor)

    service.untag(session, seg.SegmentationID, tag.TagID, actor)

    assert (
        SegmentationRepository().get_tag_link(
            session, tag.TagID, seg.SegmentationID
        )
        is None
    )


def test_untag_absent_link_is_idempotent(session):
    """untag with no link present is a no-op (no error)."""
    actor = _actor(session)
    seg = _make_segmentation(session, "t6")
    tag = _make_tag(session, actor.id)
    session.commit()

    _service().untag(session, seg.SegmentationID, tag.TagID, actor)
