"""Tests for automatic model version resolution."""

from __future__ import annotations

from eyened_orm.inference.model_versions import (
    huggingface_artifact_version,
    huggingface_pipeline_version,
    package_distribution_version,
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
