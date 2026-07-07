import pytest

from eyened_orm import Feature
from eyened_orm.repositories.feature_repository import FeatureRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import ConflictError, NotFoundError
from server.services.feature_service import FeatureService


def _make_feature(session, name: str) -> Feature:
    f = Feature(FeatureName=name)
    session.add(f)
    session.flush()
    return f


def _service(logger=None) -> FeatureService:
    return FeatureService(FeatureRepository(), logger=logger)


def _actor() -> ActingUser:
    return ActingUser(id=1, username="alice")


class FakeAuditLogger:
    """Records logging calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.inserts: list[dict] = []
        self.updates: list[dict] = []
        self.deletes: list[dict] = []

    def log_insert(self, **kwargs) -> None:
        self.inserts.append(kwargs)

    def log_update(self, **kwargs) -> None:
        self.updates.append(kwargs)

    def log_delete(self, **kwargs) -> None:
        self.deletes.append(kwargs)


class _SegBlockingRepo:
    """Hand-rolled fake forcing the 'has segmentations' guard without a real Segmentation."""

    def get_by_id(self, session, feature_id):
        f = Feature(FeatureName="Retina")
        f.FeatureID = feature_id
        return f

    def count_segmentations(self, session, feature_id):
        return 3


def test_create_feature_persists_with_subfeatures(session):
    """Creating a feature with subfeature ids writes the ordered child links."""
    child = _make_feature(session, "child")

    feature = _service().create_feature(session, "parent", [child.FeatureID], _actor())

    assert feature.FeatureName == "parent"
    assert FeatureRepository().list_subfeature_ids(session, feature.FeatureID) == [
        child.FeatureID
    ]


def test_create_feature_without_subfeatures(session):
    """Creating a feature with no subfeatures leaves it childless."""
    feature = _service().create_feature(session, "solo", None, _actor())

    assert feature.FeatureName == "solo"
    assert FeatureRepository().list_subfeature_ids(session, feature.FeatureID) == []


def test_create_feature_logs_insert(session):
    """Creating a feature emits one insert audit record naming the entity and user."""
    logger = FakeAuditLogger()

    _service(logger).create_feature(session, "solo", None, _actor())

    assert len(logger.inserts) == 1
    assert logger.inserts[0]["entity"] == "Feature"
    assert logger.inserts[0]["user"] == "alice"


def test_get_feature_returns_it(session):
    """get_feature returns the ORM object for an existing id."""
    feature = _make_feature(session, "x")
    assert _service().get_feature(session, feature.FeatureID).FeatureID == feature.FeatureID


def test_get_feature_unknown_raises_not_found(session):
    """get_feature on a missing id is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_feature(session, 999_999)


def test_list_features_orders_by_name_and_omits_counts(session):
    """list_features(with_counts=False) returns name-sorted features and an empty count map."""
    _make_feature(session, "Zeta")
    _make_feature(session, "Alpha")

    features, counts = _service().list_features(session, with_counts=False)

    assert [f.FeatureName for f in features] == ["Alpha", "Zeta"]
    assert counts == {}


def test_update_feature_changes_name(session):
    """Updating name overwrites FeatureName in place."""
    feature = _make_feature(session, "old")

    updated = _service().update_feature(
        session, feature.FeatureID, "new", None, _actor()
    )

    assert updated.FeatureName == "new"


def test_update_feature_replaces_subfeatures(session):
    """Updating subfeature_ids replaces the child link set."""
    parent = _make_feature(session, "parent")
    a = _make_feature(session, "a")
    b = _make_feature(session, "b")
    service = _service()
    service.update_feature(session, parent.FeatureID, None, [a.FeatureID], _actor())

    service.update_feature(session, parent.FeatureID, None, [b.FeatureID], _actor())

    assert FeatureRepository().list_subfeature_ids(session, parent.FeatureID) == [
        b.FeatureID
    ]


def test_update_feature_unknown_raises_not_found(session):
    """Updating a missing feature is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().update_feature(session, 999_999, "x", None, _actor())


def test_update_feature_logs_update(session):
    """Updating a feature emits one update audit record."""
    feature = _make_feature(session, "old")
    logger = FakeAuditLogger()

    _service(logger).update_feature(session, feature.FeatureID, "new", None, _actor())

    assert len(logger.updates) == 1
    assert logger.updates[0]["entity"] == "Feature"


def test_delete_feature_removes_it(session):
    """Deleting an unreferenced feature removes it from the database."""
    feature = _make_feature(session, "gone")

    _service().delete_feature(session, feature.FeatureID, _actor())

    assert FeatureRepository().get_by_id(session, feature.FeatureID) is None


def test_delete_feature_unknown_raises_not_found(session):
    """Deleting a missing feature is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().delete_feature(session, 999_999, _actor())


def test_delete_feature_blocked_by_child_link_raises_conflict(session):
    """A feature that is a child of another cannot be deleted (409 FEATURE_IS_CHILD)."""
    parent = _make_feature(session, "parent")
    child = _make_feature(session, "child")
    FeatureRepository().replace_subfeatures(session, parent.FeatureID, [child.FeatureID])

    with pytest.raises(ConflictError) as exc:
        _service().delete_feature(session, child.FeatureID, _actor())

    detail = exc.value.detail
    assert detail["code"] == "FEATURE_IS_CHILD"
    assert detail["parents"] == ["parent"]


def test_delete_feature_blocked_by_segmentations_raises_conflict(session):
    """A feature with linked segmentations cannot be deleted (409 FEATURE_HAS_SEGMENTATIONS)."""
    service = FeatureService(_SegBlockingRepo())

    with pytest.raises(ConflictError) as exc:
        service.delete_feature(session, 7, _actor())

    detail = exc.value.detail
    assert detail["code"] == "FEATURE_HAS_SEGMENTATIONS"
    assert detail["segmentation_count"] == 3


def test_delete_feature_logs_delete(session):
    """Deleting a feature emits one delete audit record."""
    feature = _make_feature(session, "gone")
    logger = FakeAuditLogger()

    _service(logger).delete_feature(session, feature.FeatureID, _actor())

    assert len(logger.deletes) == 1
    assert logger.deletes[0]["entity"] == "Feature"
