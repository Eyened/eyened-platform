"""One-time idempotent migration of legacy AttributesModel.Version strings.

For each CFI model name, sets ``Version`` on the existing row to the current
canonical version from pipeline code. If a row with that ``(ModelName, Version)``
already exists, the migration is a no-op for that model.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import AttributesModel
from eyened_orm.inference.cfi_keypoints import CFIKeypoints
from eyened_orm.inference.cfi_odfd import CFI_ODFD
from eyened_orm.inference.cfi_quality import CFI_Quality
from eyened_orm.inference.cfi_roi import FUNDUSPREP_DISTRIBUTION
from eyened_orm.inference.model_versions import (
    huggingface_artifact_version,
    huggingface_pipeline_version,
    package_distribution_version,
)


def current_cfi_model_versions() -> dict[str, str]:
    """Canonical version strings for each CFI attribute model."""
    return {
        "CFI_ROI": package_distribution_version(FUNDUSPREP_DISTRIBUTION),
        "CFI_Keypoints": huggingface_pipeline_version(*CFIKeypoints.HF_ARTIFACTS),
        "CFI_ODFD": huggingface_artifact_version(CFI_ODFD.HF_ARTIFACT),
        "CFI_Quality": huggingface_artifact_version(CFI_Quality.HF_ARTIFACT),
    }


def migrate_attributes_model_version(
    session: Session, *, model_name: str, target_version: str
) -> str:
    """Update the existing model row's version, or no-op when already canonical.

    Returns one of: ``updated``, ``skipped``, ``missing``, ``error``.
    """
    rows = list(
        session.scalars(
            select(AttributesModel).where(AttributesModel.ModelName == model_name)
        ).all()
    )

    if len(rows) == 0:
        return "missing"
    if len(rows) > 1:
        return "error"

    row = rows[0]
    if row.Version == target_version:
        return "skipped"

    row.Version = target_version
    return "updated"


def migrate_cfi_attributes_model_versions(session: Session) -> dict[str, str]:
    """Run all CFI attribute model version migrations. Safe to call repeatedly."""
    results: dict[str, str] = {}
    for model_name, target_version in current_cfi_model_versions().items():
        results[model_name] = migrate_attributes_model_version(
            session, model_name=model_name, target_version=target_version
        )
    session.flush()
    return results
