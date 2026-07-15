"""Tests for automatic model version resolution and ordering."""

from __future__ import annotations

from eyened_orm.inference.model_versions import (
    huggingface_artifact_version,
    huggingface_pipeline_version,
    package_distribution_version,
    version_at_least,
    version_sort_key,
)


def test_package_distribution_version_fundusprep():
    version = package_distribution_version("retinalysis-fundusprep")
    assert version.count(".") >= 1


def test_huggingface_artifact_version_nested_path():
    assert (
        huggingface_artifact_version("Eyened/vascx:odfd/odfd_march25.pt")
        == "Eyened/vascx/odfd/odfd_march25"
    )


def test_huggingface_pipeline_version_joins_sorted_artifacts():
    version = huggingface_pipeline_version(
        "Eyened/vascx:discedge/discedge_july24.pt",
        "Eyened/vascx:fovea/fovea_july24.pt",
    )
    assert version == (
        "Eyened/vascx/discedge/discedge_july24+Eyened/vascx/fovea/fovea_july24"
    )


def test_version_at_least_semver():
    assert version_at_least("1.1.0", "1.0")
    assert version_at_least("2.0", "1.0")
    assert not version_at_least("0.9", "1.0")


def test_version_sort_key_orders_within_kind():
    assert version_sort_key("1.1.0") > version_sort_key("1.0.0")
    assert version_sort_key("Eyened/vascx/odfd/odfd_march25") > version_sort_key(
        "Eyened/vascx/odfd/odfd_jan24"
    )


def test_version_sort_key_kinds_are_not_mixed_for_min_version():
    """Semver and HF artifact ids are only compared among same-kind versions."""
    assert version_at_least("1.1.0", "1.0.0")
    assert not version_at_least("0.9.0", "1.0.0")
