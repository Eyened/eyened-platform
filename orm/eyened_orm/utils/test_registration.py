"""Tests for registration JSON key handling."""

from __future__ import annotations

from eyened_orm.utils.registration import (
    are_connected,
    collect_legacy_instance_ids,
    collect_registration_seed_transforms,
    get_processed_edges,
    graph_from_transforms,
    normalize_registration_key,
    normalize_registration_transforms,
    registration_image_key,
)


class _FakeImage:
    def __init__(self, instance_id: int, public_id: str):
        self.ImageInstanceID = instance_id
        self.PublicID = public_id


class _FakeAttributeValue:
    def __init__(self, value):
        self.ValueJSON = value


def test_registration_image_key_uses_public_id():
    image = _FakeImage(123, "pubabc123456")
    assert registration_image_key(image) == "pubabc123456"


def test_collect_legacy_instance_ids():
    transforms = [
        {"image1": 1, "image2": "2", "transform": {}},
        {"image1": "alreadyPublic", "image2": 3, "transform": {}},
    ]
    assert collect_legacy_instance_ids(transforms) == {1, 2, 3}


def test_normalize_registration_transforms():
    id_to_public = {1: "pub1", 2: "pub2", 3: "pub3"}
    transforms = [
        {
            "image1": 1,
            "image2": 2,
            "transform": {"type": "CompositeTransform", "transforms": []},
        },
    ]
    normalized = normalize_registration_transforms(transforms, id_to_public)
    assert normalized[0]["image1"] == "pub1"
    assert normalized[0]["image2"] == "pub2"


def test_get_processed_edges_normalizes_legacy_keys():
    id_to_public = {1: "pub1", 2: "pub2", 3: "pub3"}
    av = _FakeAttributeValue(
        [
            {"image1": 1, "image2": 2, "transform": {}},
            {"image1": 2, "image2": 3, "transform": {}},
        ]
    )
    graph = get_processed_edges(av, id_to_public)
    assert "pub1" in graph
    assert "pub2" in graph
    assert "pub3" in graph


def test_graph_from_transforms_matches_get_processed_edges():
    id_to_public = {1: "pub1", 2: "pub2"}
    transforms = [{"image1": 1, "image2": 2, "transform": {}}]
    av = _FakeAttributeValue(transforms)
    assert graph_from_transforms(transforms, id_to_public) == get_processed_edges(
        av, id_to_public
    )


def test_collect_registration_seed_skips_when_replace():
    assert collect_registration_seed_transforms(None, None, 1, replace=True) == []


def test_collect_registration_seed_merges_all_model_versions(monkeypatch):
    """Seed for skip logic includes AttributeValues from every model version."""
    av_old = _FakeAttributeValue(
        [{"image1": "pubA", "image2": "pubB", "transform": {}}]
    )
    av_new = _FakeAttributeValue([])

    def _by_columns(session, **kwargs):
        assert kwargs == {"PatientID": 7, "AttributeID": 99}
        return [av_old, av_new]

    monkeypatch.setattr(
        "eyened_orm.utils.registration.AttributeValue.by_columns", _by_columns
    )
    seed = collect_registration_seed_transforms(
        session=object(),
        patient=type("P", (), {"PatientID": 7})(),
        attribute_id=99,
        replace=False,
    )
    assert seed == av_old.ValueJSON


def test_seed_graph_skips_transitive_pairs_from_prior_model():
    """Connectivity skip treats edges from another model's output as processed."""
    seed = [
        {"image1": "pubA", "image2": "pubB", "transform": {}},
        {"image1": "pubB", "image2": "pubC", "transform": {}},
    ]
    graph = graph_from_transforms(seed)
    assert are_connected("pubA", "pubC", graph)
    assert not are_connected("pubA", "pubD", graph)


def test_normalize_registration_key_passthrough_public_id():
    id_to_public = {1: "pub1"}
    assert normalize_registration_key("pub1", id_to_public) == "pub1"
