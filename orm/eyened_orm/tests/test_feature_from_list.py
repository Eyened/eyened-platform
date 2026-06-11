from __future__ import annotations

import pytest
from sqlalchemy import func, select

from eyened_orm.segmentation import Feature, FeatureFeatureLink


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_creates_leaf_feature(session):
    feature = Feature.from_list(session, "Standalone")
    session.flush()

    assert feature.FeatureName == "Standalone"
    assert feature.subfeatures == {}
    assert _count(session, Feature) == 1
    assert _count(session, FeatureFeatureLink) == 0


def test_leaf_feature_is_idempotent(session):
    first = Feature.from_list(session, "Standalone")
    session.flush()
    feature_id = first.FeatureID

    second = Feature.from_list(session, "Standalone")
    session.flush()

    assert second.FeatureID == feature_id
    assert _count(session, Feature) == 1
    assert _count(session, FeatureFeatureLink) == 0


def test_creates_feature_hierarchy(session):
    sub_features = ["RNFL", "GCL", "IPL"]
    feature = Feature.from_list(session, "Retinal Layers", sub_features)
    session.flush()

    assert feature.FeatureName == "Retinal Layers"
    assert feature.subfeatures == {1: "RNFL", 2: "GCL", 3: "IPL"}
    assert _count(session, Feature) == 4
    assert _count(session, FeatureFeatureLink) == 3


def test_repeated_call_with_same_subfeatures_is_idempotent(session):
    sub_features = ["RNFL", "GCL", "IPL"]
    first = Feature.from_list(session, "Retinal Layers", sub_features)
    session.flush()
    feature_id = first.FeatureID
    feature_count = _count(session, Feature)
    link_count = _count(session, FeatureFeatureLink)
    subfeatures = first.subfeatures

    second = Feature.from_list(session, "Retinal Layers", sub_features)
    session.flush()

    assert second.FeatureID == feature_id
    assert second.subfeatures == subfeatures
    assert _count(session, Feature) == feature_count
    assert _count(session, FeatureFeatureLink) == link_count


def test_removes_subfeature_links(session):
    Feature.from_list(session, "Retinal Layers", ["RNFL", "GCL", "IPL"])
    session.flush()

    feature = Feature.from_list(session, "Retinal Layers", ["RNFL", "IPL"])
    session.flush()

    assert feature.subfeatures == {1: "RNFL", 2: "IPL"}
    assert _count(session, FeatureFeatureLink) == 2
    assert Feature.by_name(session, "GCL") is not None


def test_adds_subfeature_links(session):
    Feature.from_list(session, "Retinal Layers", ["RNFL"])
    session.flush()

    feature = Feature.from_list(session, "Retinal Layers", ["RNFL", "GCL", "IPL"])
    session.flush()

    assert feature.subfeatures == {1: "RNFL", 2: "GCL", 3: "IPL"}
    assert _count(session, FeatureFeatureLink) == 3


def test_reorders_subfeature_links(session):
    Feature.from_list(session, "Retinal Layers", ["RNFL", "GCL", "IPL"])
    session.flush()

    feature = Feature.from_list(session, "Retinal Layers", ["IPL", "RNFL", "GCL"])
    session.flush()

    assert feature.subfeatures == {1: "IPL", 2: "RNFL", 3: "GCL"}
    assert _count(session, FeatureFeatureLink) == 3


def test_supports_duplicate_subfeature_names(session):
    feature = Feature.from_list(session, "Dupes", ["A", "A"])
    session.flush()

    assert feature.subfeatures == {1: "A", 2: "A"}
    assert _count(session, Feature) == 2
    assert _count(session, FeatureFeatureLink) == 2


def test_verbose_reports_no_changes(capsys, session):
    sub_features = ["RNFL", "GCL"]
    Feature.from_list(session, "Retinal Layers", sub_features, verbose=True)
    session.flush()

    Feature.from_list(session, "Retinal Layers", sub_features, verbose=True)
    session.flush()

    output = capsys.readouterr().out
    assert "Created feature: Retinal Layers" in output
    assert "Created sub-feature: RNFL" in output
    assert "sub-features already match; no changes" in output


def test_verbose_reports_link_changes(capsys, session):
    Feature.from_list(session, "Retinal Layers", ["RNFL", "GCL"], verbose=True)
    session.flush()

    Feature.from_list(session, "Retinal Layers", ["GCL"], verbose=True)
    session.flush()

    output = capsys.readouterr().out
    assert "Removed link: Retinal Layers[1] -> RNFL" in output
    assert "Added link: Retinal Layers[1] -> GCL" in output


def test_raises_on_unsupported_sub_features_type(session):
    with pytest.raises(ValueError, match="Unsupported sub_features type"):
        Feature.from_list(session, "Bad", {1: "RNFL"})
