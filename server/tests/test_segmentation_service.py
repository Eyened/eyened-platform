import numpy as np
import pytest
from sqlalchemy import text

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


class FakeAudit:
    """Records .record() calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


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


def _service(
    session,
    store: FakeSegmentationDataStore | None = None,
    audit: FakeAudit | None = None,
) -> SegmentationService:
    return SegmentationService(
        SegmentationRepository(session),
        ImageInstanceRepository(session),
        TagRepository(session),
        store or FakeSegmentationDataStore(),
        audit=audit,
    )


def _model_service(
    session,
    store: FakeSegmentationDataStore | None = None,
) -> ModelSegmentationService:
    return ModelSegmentationService(
        ModelSegmentationRepository(session), store or FakeSegmentationDataStore()
    )


def _actor(session, key: str = "actor") -> ActingUser:
    from eyened_orm import Creator

    creator = Creator(CreatorName=f"u-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    return ActingUser(id=creator.CreatorID, username=creator.CreatorName)


def test_get_segmentation_unknown_raises_not_found(session):
    """get_segmentation on a missing id raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).get_segmentation(999_999)


def test_read_data_unknown_raises_not_found(session):
    """read_data on a missing id raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).read_data(999_999)


def test_read_data_empty_returns_none(session):
    """read_data on a row with no stored array returns None (no storage hit)."""
    seg = _make_segmentation(session, "r1")  # ZarrArrayIndex is None
    session.commit()

    assert _service(session).read_data(seg.SegmentationID) is None


def test_model_read_data_unknown_raises_not_found(session):
    """ModelSegmentationService.read_data on a missing id raises NotFoundError."""
    with pytest.raises(NotFoundError):
        _model_service(session).read_data(999_999)


from eyened_orm.segmentation import DataRepresentation, Datatype


def test_create_persists_and_writes(session):
    """create builds the row, writes via the store, and persists it.

    Pins the store-vs-DB order: the repo add()+flush() assigns the PK before
    self.store.write() runs (the fake store's ZarrArrayIndex assignment would
    have nothing to key off if the PK were not yet assigned).
    """
    actor = _actor(session)
    seg = _make_segmentation(session, "c0")
    image_id = seg.ImageInstance.PublicID
    session.commit()
    store = FakeSegmentationDataStore()

    created = _service(session, store).create(
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


def test_create_writes_back_the_store_assigned_zarr_index(session):
    """create's post-store-write mutations reach the database.

    store.write() sets ZarrArrayIndex (and can replace ScanIndices) *after*
    repository.add() has already flushed the INSERT, so those mutations need
    their own write-back. The sibling test above asserts on the returned
    object, which cannot see this: the identity map hands back the same
    instance whether or not anything was flushed. This reads the row back with
    raw SQL, which bypasses the identity map and does not autoflush (the test
    session matches production's autoflush=False).

    Discriminator: dropping repository.save(segmentation) from create() makes
    this fail with ZarrArrayIndex still NULL.
    """
    actor = _actor(session)
    seg = _make_segmentation(session, "c-wb")
    image_id = seg.ImageInstance.PublicID
    session.commit()

    created = _service(session, FakeSegmentationDataStore()).create(
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

    stored = session.execute(
        text("SELECT ZarrArrayIndex FROM Segmentation WHERE SegmentationID = :id"),
        {"id": created.SegmentationID},
    ).scalar_one()
    assert stored == 0  # the index the fake store assigned, as written to the row


def test_create_empty_array_fills_zeros(session):
    """create with array=None fills a zeros volume from the image shape."""
    actor = _actor(session)
    seg = _make_segmentation(session, "c1")
    image_id = seg.ImageInstance.PublicID
    session.commit()

    created = _service(session).create(
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


def test_create_unknown_image_raises_not_found(session):
    """create with an unresolvable image_id raises NotFoundError (-> 404)."""
    actor = _actor(session)
    seg = _make_segmentation(session, "c2")
    session.commit()
    with pytest.raises(NotFoundError):
        _service(session).create(
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
        _service(session).create(
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


def test_create_logs_insert(session):
    """create emits one INSERT audit record naming the entity and its id."""
    actor = _actor(session)
    seg = _make_segmentation(session, "ci1")
    image_id = seg.ImageInstance.PublicID
    session.commit()
    audit = FakeAudit()

    created = _service(session, audit=audit).create(
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

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "INSERT"
    assert rec["entity"] == "Segmentation"
    assert rec["entity_id"] == created.SegmentationID


def test_write_data_unknown_raises_not_found(session):
    """write_data on a missing id raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).write_data(
            999_999, np.zeros((1, 4, 4), dtype=np.uint8), actor=_actor(session)
        )


def test_write_data_persists_zarr_index(session):
    """write_data stores via the port and persists the ZarrArrayIndex.

    Pins the store-vs-DB order: store.write() (which assigns ZarrArrayIndex)
    runs BEFORE the repo persists — unchanged from pre-refactor.
    """
    actor = _actor(session)
    seg = _make_segmentation(session, "w1")
    session.commit()
    store = FakeSegmentationDataStore()

    updated = _service(session, store).write_data(
        seg.SegmentationID, np.zeros((1, 4, 4), dtype=np.uint8), actor=actor
    )

    assert updated.ZarrArrayIndex == 0


def test_write_data_logs_update(session):
    """write_data's UPDATE audit carries no changes payload — pre-refactor
    log_simple never included field detail for this high-frequency op;
    preserved as-is."""
    actor = _actor(session)
    seg = _make_segmentation(session, "wu1")
    session.commit()
    audit = FakeAudit()

    _service(session, audit=audit).write_data(
        seg.SegmentationID, np.zeros((1, 4, 4), dtype=np.uint8), actor=actor
    )

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "Segmentation"
    assert rec["entity_id"] == seg.SegmentationID
    assert "changes" not in rec


class _OrderRecordingModelRepo:
    """Fake ModelSegmentationRepository (no DB) that returns a fixed item and
    records the save() call — method name plus the entity it was handed — into
    a list shared with the fake store below."""

    def __init__(self, item, calls: list) -> None:
        self._item = item
        self._calls = calls

    def get_by_id(self, model_segmentation_id: int):
        return self._item

    def save(self, model_segmentation) -> None:
        self._calls.append(("save", model_segmentation))


class _OrderRecordingStore:
    """Fake store that records into the same shared call-order list."""

    def __init__(self, calls: list) -> None:
        self._calls = calls

    def write(self, item, data, *, axis=None, slice_index=None):
        self._calls.append(("store.write", item))


def test_model_write_data_store_write_precedes_repo_persist():
    """Pins the store-vs-DB order for the model item: store.write() must run
    BEFORE self.repository.save() — unchanged from pre-refactor
    (``self.store.write(...)`` then ``session.add(item)``). Uses fakes (no
    DB) since building a full ModelSegmentation FK graph adds no value here
    — only the call order is under test.
    """
    calls: list = []
    item = object()

    ModelSegmentationService(
        _OrderRecordingModelRepo(item, calls), _OrderRecordingStore(calls)
    ).write_data(1, np.zeros((1, 4, 4), dtype=np.uint8))

    assert calls == [("store.write", item), ("save", item)]


def test_soft_delete_sets_inactive(session):
    """soft_delete flags the row Inactive."""
    actor = _actor(session)
    seg = _make_segmentation(session, "d1")
    session.commit()

    _service(session).soft_delete(seg.SegmentationID, actor)

    assert seg.Inactive is True


def test_soft_delete_unknown_raises_not_found(session):
    """soft_delete on a missing id raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).soft_delete(999_999, _actor(session))


def test_soft_delete_logs_delete(session):
    """soft_delete's DELETE audit carries a snapshot of the segmentation's fields."""
    actor = _actor(session)
    seg = _make_segmentation(session, "sd1")
    session.commit()
    audit = FakeAudit()

    _service(session, audit=audit).soft_delete(seg.SegmentationID, actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "DELETE"
    assert rec["entity"] == "Segmentation"
    assert rec["entity_id"] == seg.SegmentationID
    assert rec["changes"]["feature_id"] == seg.FeatureID


def test_patch_applies_threshold_and_feature(session):
    """patch updates threshold and feature_id on the row."""
    actor = _actor(session)
    seg = _make_segmentation(session, "p1")
    other = _make_segmentation(session, "p1-feat")
    session.commit()

    updated = _service(session).patch(
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
        _service(session).patch(
            999_999,
            reference_segmentation_id=None,
            feature_id=None,
            threshold=1.0,
            actor=_actor(session),
        )


def test_patch_logs_true_diff(session):
    """patch's UPDATE audit carries a true {old, new} diff per changed column
    — the sanctioned removal of the pre-refactor double-assignment quirk,
    where reference_segmentation_id/feature_id were applied before the
    change-string was built, so they logged '<new> -> <new>' instead of the
    true old value. AuditService.snapshot/diff now reports true old/new for all three
    fields."""
    actor = _actor(session)
    seg = _make_segmentation(session, "pd1")
    other = _make_segmentation(session, "pd1-feat")
    session.commit()
    old_feature_id = seg.FeatureID
    audit = FakeAudit()

    _service(session, audit=audit).patch(
        seg.SegmentationID,
        reference_segmentation_id=None,
        feature_id=other.FeatureID,
        threshold=0.5,
        actor=actor,
    )

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "Segmentation"
    assert rec["entity_id"] == seg.SegmentationID
    assert rec["changes"] == {
        "FeatureID": {"old": old_feature_id, "new": other.FeatureID},
        "Threshold": {"old": None, "new": 0.5},
    }


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

    link = _service(session).tag(seg.SegmentationID, tag.TagID, actor)

    assert link.TagID == tag.TagID
    assert link.SegmentationID == seg.SegmentationID
    assert link.Tag.TagID == tag.TagID


def test_tag_unknown_segmentation_raises_not_found(session):
    """tag on a missing segmentation raises NotFoundError (-> 404)."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    session.commit()
    with pytest.raises(NotFoundError):
        _service(session).tag(999_999, tag.TagID, actor)


def test_tag_unknown_tag_raises_not_found(session):
    """tag with an unknown tag id raises NotFoundError (-> 404)."""
    actor = _actor(session)
    seg = _make_segmentation(session, "t2")
    session.commit()
    with pytest.raises(NotFoundError):
        _service(session).tag(seg.SegmentationID, 999_999, actor)


def test_tag_wrong_type_raises_bad_request(session):
    """tag with a non-Segmentation tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    seg = _make_segmentation(session, "t3")
    tag = _make_tag(session, actor.id, tag_type=TagType.ImageInstance)
    session.commit()
    with pytest.raises(BadRequestError):
        _service(session).tag(seg.SegmentationID, tag.TagID, actor)


def test_tag_is_idempotent(session):
    """A second tag with the same (seg, tag) returns the existing link, no dup."""
    actor = _actor(session)
    seg = _make_segmentation(session, "t4")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service(session)

    service.tag(seg.SegmentationID, tag.TagID, actor)
    link = service.tag(seg.SegmentationID, tag.TagID, actor)

    assert link.TagID == tag.TagID


def test_tag_logs_insert(session):
    """tag's INSERT audit folds the (tag_id, segmentation_id) identity into
    changes — SegmentationTagLink has a composite PK, so entity_id is null;
    identity must live in changes (matches untag's DELETE below) or the audit
    row is unidentifiable. Keys match the pre-refactor log_insert's fields."""
    actor = _actor(session)
    seg = _make_segmentation(session, "ti1")
    tag = _make_tag(session, actor.id)
    session.commit()
    audit = FakeAudit()

    _service(session, audit=audit).tag(seg.SegmentationID, tag.TagID, actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "INSERT"
    assert rec["entity"] == "SegmentationTagLink"
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "segmentation_id": seg.SegmentationID,
    }


def test_tag_idempotent_replay_does_not_reaudit(session):
    """A second tag() call on an existing link is a pure lookup — no audit
    (no UPDATE branch exists for this composite-PK link; comment is ignored)."""
    actor = _actor(session)
    seg = _make_segmentation(session, "ti2")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service(session)
    service.tag(seg.SegmentationID, tag.TagID, actor)
    audit = FakeAudit()

    _service(session, audit=audit).tag(seg.SegmentationID, tag.TagID, actor)

    assert audit.records == []


def test_untag_removes_link(session):
    """untag deletes the link for that (segmentation, tag)."""
    actor = _actor(session)
    seg = _make_segmentation(session, "t5")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service(session)
    service.tag(seg.SegmentationID, tag.TagID, actor)

    service.untag(seg.SegmentationID, tag.TagID, actor)

    assert (
        SegmentationRepository(session).get_tag_link(
            tag.TagID, seg.SegmentationID
        )
        is None
    )


def test_untag_absent_link_is_idempotent(session):
    """untag with no link present is a no-op (no error)."""
    actor = _actor(session)
    seg = _make_segmentation(session, "t6")
    tag = _make_tag(session, actor.id)
    session.commit()

    _service(session).untag(seg.SegmentationID, tag.TagID, actor)


def test_untag_logs_delete(session):
    """untag's DELETE audit carries the removed link's identity + creator_id
    — matches the pre-refactor log_delete's deleted_data keys exactly."""
    actor = _actor(session)
    seg = _make_segmentation(session, "ut1")
    tag = _make_tag(session, actor.id)
    session.commit()
    service = _service(session)
    service.tag(seg.SegmentationID, tag.TagID, actor)
    audit = FakeAudit()

    _service(session, audit=audit).untag(seg.SegmentationID, tag.TagID, actor)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "DELETE"
    assert rec["entity"] == "SegmentationTagLink"
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "segmentation_id": seg.SegmentationID,
        "creator_id": actor.id,
    }
