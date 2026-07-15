"""Tests for attribute inference pipeline model registration."""

from __future__ import annotations

from eyened_orm import AttributesModel
from eyened_orm.inference.cfi_odfd import CFI_ODFD
import torch


def test_attributes_model_description_synced_on_pipeline_init(session):
    """get_or_create update_values keeps Model.Description in sync with pipeline code."""
    existing = AttributesModel(
        ModelName="CFI_ODFD",
        Version="odfd_march25",
        Description="old description",
    )
    session.add(existing)
    session.commit()

    CFI_ODFD(session, device=torch.device("cpu"), n_workers=1)

    session.refresh(existing)
    assert existing.Description == CFI_ODFD.model_description
