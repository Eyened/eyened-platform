from eyened_orm import Feature
from eyened_orm.segmentation import FeatureFeatureLink


def _feat(session, name: str) -> Feature:
    f = Feature(FeatureName=name)
    session.add(f)
    session.flush()
    return f


def test_subfeature_ids_list_returns_child_ids_in_index_order(session):
    """subfeature_ids_list returns child ids ordered by FeatureIndex, not id."""
    parent = _feat(session, "parent")
    a = _feat(session, "a")
    b = _feat(session, "b")
    # Link out of natural id order to prove ordering is by FeatureIndex.
    session.add(
        FeatureFeatureLink(ParentFeatureID=parent.FeatureID, ChildFeatureID=b.FeatureID, FeatureIndex=0)
    )
    session.add(
        FeatureFeatureLink(ParentFeatureID=parent.FeatureID, ChildFeatureID=a.FeatureID, FeatureIndex=1)
    )
    session.flush()
    # The parent's FeatureAssociations collection was initialized empty when the
    # object was created; expire it so the property reloads the links from the DB
    # (this is exactly what happens for a feature freshly loaded in a request).
    session.expire(parent, ["FeatureAssociations"])

    assert parent.subfeature_ids_list == [b.FeatureID, a.FeatureID]


def test_subfeature_ids_list_empty_without_children(session):
    """A feature with no child links has an empty subfeature_ids_list."""
    assert _feat(session, "solo").subfeature_ids_list == []
