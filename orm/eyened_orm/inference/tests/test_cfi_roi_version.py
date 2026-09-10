"""Tests for CFI_ROI dynamic package version."""

from __future__ import annotations

from eyened_orm.inference.cfi_roi import CFI_ROI, FUNDUSPREP_DISTRIBUTION
from eyened_orm.inference.model_versions import package_distribution_version


def test_cfi_roi_uses_installed_fundusprep_version(session):
    pipeline = CFI_ROI(session, n_workers=1)
    expected = package_distribution_version(FUNDUSPREP_DISTRIBUTION)
    assert pipeline.model_version == expected
    assert pipeline.model.Version == expected
