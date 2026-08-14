from eyened_orm import Feature
from eyened_orm.repositories.feature_repository import FeatureRepository


def _feat(session, name: str) -> Feature:
    f = Feature(FeatureName=name)
    session.add(f)
    session.flush()
    return f


def test_list_all_orders_by_name(session):
    """list_all returns every feature sorted by FeatureName ascending."""
    _feat(session, "Zeta")
    _feat(session, "Alpha")
    _feat(session, "Mu")
    names = [f.FeatureName for f in FeatureRepository(session).list_all()]
    assert names == ["Alpha", "Mu", "Zeta"]


def test_replace_subfeatures_sets_ordered_children(session):
    """replace_subfeatures writes child links preserving list order as 0-based FeatureIndex."""
    parent = _feat(session, "parent")
    a = _feat(session, "a")
    b = _feat(session, "b")
    repo = FeatureRepository(session)

    repo.replace_subfeatures(parent.FeatureID, [b.FeatureID, a.FeatureID])

    assert repo.list_subfeature_ids(parent.FeatureID) == [b.FeatureID, a.FeatureID]


def test_replace_subfeatures_overwrites_previous(session):
    """replace_subfeatures clears prior links before writing the new set."""
    parent = _feat(session, "parent")
    a = _feat(session, "a")
    b = _feat(session, "b")
    repo = FeatureRepository(session)
    repo.replace_subfeatures(parent.FeatureID, [a.FeatureID])

    repo.replace_subfeatures(parent.FeatureID, [b.FeatureID])

    assert repo.list_subfeature_ids(parent.FeatureID) == [b.FeatureID]


def test_parent_names_of_child_lists_parents(session):
    """parent_names_of_child returns the names of features linking to this child."""
    parent = _feat(session, "parent")
    child = _feat(session, "child")
    FeatureRepository(session).replace_subfeatures(parent.FeatureID, [child.FeatureID])

    assert FeatureRepository(session).parent_names_of_child(child.FeatureID) == ["parent"]


def test_count_segmentations_zero_when_none(session):
    """count_segmentations returns 0 for a feature with no linked segmentations."""
    f = _feat(session, "lonely")
    assert FeatureRepository(session).count_segmentations(f.FeatureID) == 0


def test_segmentation_counts_empty_when_no_segmentations(session):
    """segmentation_counts returns an empty mapping when no segmentations exist."""
    _feat(session, "x")
    assert FeatureRepository(session).segmentation_counts() == {}
