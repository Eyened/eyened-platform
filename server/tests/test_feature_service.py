import pytest

from eyened_orm import Feature
from eyened_orm.repositories.feature_repository import FeatureRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import ConflictError, NotFoundError
from server.services.feature_service import FeatureService
from eyened_orm.utils.factories import admin_scope


def _make_feature(session, name: str) -> Feature:
    f = Feature(FeatureName=name)
    session.add(f)
    session.flush()
    return f


def _service(
    session, actor: ActingUser | None = None, *, audit=None
) -> FeatureService:
    scope = (
        admin_scope(actor_id=actor.id, username=actor.username)
        if actor is not None
        else admin_scope()
    )
    return FeatureService(
        FeatureRepository(session, scope=scope),
        scope=scope,
        audit=audit,
    )


class FakeAudit:
    """Records .record() calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


class _SegBlockingRepo:
    """Hand-rolled fake forcing the 'has segmentations' guard without a real Segmentation."""

    def get_by_id(self, feature_id):
        f = Feature(FeatureName="Retina")
        f.FeatureID = feature_id
        return f

    def count_segmentations(self, feature_id):
        return 3


def test_create_feature_persists_with_subfeatures(session):
    """Creating a feature with subfeature ids writes the ordered child links."""
    child = _make_feature(session, "child")

    feature = _service(session).create_feature("parent", [child.FeatureID])

    assert feature.FeatureName == "parent"
    assert FeatureRepository(session, scope=admin_scope()).list_subfeature_ids(feature.FeatureID) == [
        child.FeatureID
    ]


def test_create_feature_without_subfeatures(session):
    """Creating a feature with no subfeatures leaves it childless."""
    feature = _service(session).create_feature("solo", None)

    assert feature.FeatureName == "solo"
    assert FeatureRepository(session, scope=admin_scope()).list_subfeature_ids(feature.FeatureID) == []


def test_create_feature_logs_insert(session):
    """Creating a feature emits one INSERT audit record naming the entity."""
    actor = ActingUser(id=7, username="feature-actor")
    audit = FakeAudit()

    _service(session, actor, audit=audit).create_feature("solo", None)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "INSERT"
    assert audit.records[0]["entity"] == "Feature"
    # Pins the service's `self._actor = ActingUser.from_scope(scope)` line.
    # Without it the service can attribute every audit row to the wrong user
    # and stay green -- the audit trail is the artefact, so it needs the pin.
    assert audit.records[0]["actor"] == actor


def test_get_feature_unknown_raises_not_found(session):
    """get_feature on a missing id is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).get_feature(999_999)


def test_list_features_orders_by_name_and_omits_counts(session):
    """list_features(with_counts=False) returns name-sorted features and an empty count map."""
    _make_feature(session, "Zeta")
    _make_feature(session, "Alpha")

    features, counts = _service(session).list_features(with_counts=False)

    assert [f.FeatureName for f in features] == ["Alpha", "Zeta"]
    assert counts == {}


def test_update_feature_changes_name(session):
    """Updating name overwrites FeatureName in place."""
    feature = _make_feature(session, "old")

    updated = _service(session).update_feature(feature.FeatureID, "new", None)

    assert updated.FeatureName == "new"


def test_update_feature_replaces_subfeatures(session):
    """Updating subfeature_ids replaces the child link set."""
    parent = _make_feature(session, "parent")
    a = _make_feature(session, "a")
    b = _make_feature(session, "b")
    service = _service(session)
    service.update_feature(parent.FeatureID, None, [a.FeatureID])

    service.update_feature(parent.FeatureID, None, [b.FeatureID])

    assert FeatureRepository(session, scope=admin_scope()).list_subfeature_ids(parent.FeatureID) == [
        b.FeatureID
    ]


def test_update_feature_unknown_raises_not_found(session):
    """Updating a missing feature is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).update_feature(999_999, "x", None)


def test_update_feature_logs_rename_as_diff(session):
    """Renaming emits an UPDATE record whose changes are the diff-shaped {old, new}."""
    feature = _make_feature(session, "old")
    audit = FakeAudit()

    _service(session, audit=audit).update_feature(feature.FeatureID, "new", None)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "UPDATE"
    assert audit.records[0]["entity"] == "Feature"
    assert audit.records[0]["changes"] == {"FeatureName": {"old": "old", "new": "new"}}


def test_update_feature_logs_both_name_and_subfeatures_diff(session):
    """A combined rename + relink records both diffs (proves diff() runs before the
    replace_subfeatures() flush that would otherwise clear the pending name history)."""
    parent = _make_feature(session, "old")
    child = _make_feature(session, "child")
    audit = FakeAudit()

    _service(session, audit=audit).update_feature(
        parent.FeatureID, "new", [child.FeatureID]
    )

    assert audit.records[0]["changes"] == {
        "FeatureName": {"old": "old", "new": "new"},
        "subfeature_ids": {"old": [], "new": [child.FeatureID]},
    }


def test_delete_feature_removes_it(session):
    """Deleting an unreferenced feature removes it from the database."""
    feature = _make_feature(session, "gone")

    _service(session).delete_feature(feature.FeatureID)

    assert FeatureRepository(session, scope=admin_scope()).get_by_id(feature.FeatureID) is None


def test_delete_feature_unknown_raises_not_found(session):
    """Deleting a missing feature is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).delete_feature(999_999)


def test_delete_feature_blocked_by_child_link_raises_conflict(session):
    """A feature that is a child of another cannot be deleted (409 FEATURE_IS_CHILD)."""
    parent = _make_feature(session, "parent")
    child = _make_feature(session, "child")
    FeatureRepository(session, scope=admin_scope()).replace_subfeatures(parent.FeatureID, [child.FeatureID])

    with pytest.raises(ConflictError) as exc:
        _service(session).delete_feature(child.FeatureID)

    detail = exc.value.detail
    assert detail["code"] == "FEATURE_IS_CHILD"
    assert detail["parents"] == ["parent"]


def test_delete_feature_blocked_by_segmentations_raises_conflict(session):
    """A feature with linked segmentations cannot be deleted (409 FEATURE_HAS_SEGMENTATIONS)."""
    service = FeatureService(_SegBlockingRepo(), scope=admin_scope())

    with pytest.raises(ConflictError) as exc:
        service.delete_feature(7)

    detail = exc.value.detail
    assert detail["code"] == "FEATURE_HAS_SEGMENTATIONS"
    assert detail["segmentation_count"] == 3


def test_delete_feature_logs_delete(session):
    """Deleting a feature emits one DELETE audit record."""
    feature = _make_feature(session, "gone")
    audit = FakeAudit()

    _service(session, audit=audit).delete_feature(feature.FeatureID)

    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "DELETE"
    assert audit.records[0]["entity"] == "Feature"
