from __future__ import annotations

from typing import Any

from eyened_orm.importer.importer_dtos import ImportRow

from .io import infer_storage_format


def step_apply_defaults(row: ImportRow, defaults: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for key, value in defaults.items():
        if getattr(row, key, None) is None:
            updates[key] = value
    return updates


def step_infer_image_storage_format(row: ImportRow) -> dict[str, Any]:
    if row.object_key and not row.image_storage_format:
        return {"image_storage_format": infer_storage_format(row.object_key)}
    return {}
