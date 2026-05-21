from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from eyened_orm.importer.importer_dtos import ImportRow

from . import steps
from .dicom_meta import dicom_header_patches_from_bytes
from .hashes import md5_hex, sha256_bytes
from .image_meta import raster_image_header_patches_from_bytes
from .storage_io import try_read_storage_object_bytes
from .thumbnail_util import allocate_thumbnail_path, save_thumbnails_from_bytes


def _merge_missing(state: dict[str, Any], patch: dict[str, Any]) -> None:
    for k, v in patch.items():
        if v is None:
            continue
        if state.get(k) is None:
            state[k] = v


@dataclass
class PreparationOptions:
    """
    Controls optional row preparation before import (seeding/building).

    Defaults preserve existing behavior: infer storage format from object_key
    and fill missing fields from ``defaults``.
    """

    infer_image_format: bool = True
    defaults: Optional[dict[str, Any]] = None
    read_image_header: bool = False
    read_dicom_header: bool = False
    compute_storage_hash: bool = False
    compute_storage_checksum: bool = False
    generate_thumbnails: bool = False
    raw_loader: Optional[Callable[[ImportRow], bytes | None]] = None


def _needs_raw_bytes(opts: PreparationOptions) -> bool:
    return (
        opts.read_dicom_header
        or opts.read_image_header
        or opts.compute_storage_hash
        or opts.compute_storage_checksum
        or opts.generate_thumbnails
    )


def _load_raw_bytes(state: dict[str, Any], opts: PreparationOptions) -> bytes | None:
    row = ImportRow.model_validate(state)
    if opts.raw_loader is not None:
        return opts.raw_loader(row)
    return try_read_storage_object_bytes(
        state.get("storage_backend_key"), state.get("object_key")
    )


def prepare_rows(
    rows: Sequence[ImportRow],
    *,
    infer_image_format: bool = True,
    defaults: Optional[dict[str, Any]] = None,  
    options: Optional[PreparationOptions] = None,
) -> list[ImportRow]:
    """ 
    Enrich ``ImportRow`` instances in-memory before ``plan_import``.

    If ``options`` is given, it fully defines behavior (``infer_image_format`` /
    ``defaults`` keyword args are ignored). Otherwise keywords build a
    ``PreparationOptions`` instance for backward compatibility.

    Optional steps read bytes via ``EYENED_STORAGE_MOUNTS`` (``storage_backend_key`` +
    ``object_key``), or via ``PreparationOptions.raw_loader`` (e.g. post-import
    enrichment using :func:`enrichment.raw_loader_from_image_instance`).
    """
    if options is None:
        opts = PreparationOptions(
            infer_image_format=infer_image_format,
            defaults=defaults,
        )
    else:
        opts = options

    _defaults = opts.defaults or {}
    prepared: list[ImportRow] = []

    for row in rows:
        state: dict[str, Any] = {**row.model_dump()}

        if opts.infer_image_format:
            r = ImportRow.model_validate(state)
            _merge_missing(state, steps.step_infer_image_storage_format(r))

        _merge_missing(state, steps.step_apply_defaults(ImportRow.model_validate(state), _defaults))

        raw: bytes | None = None
        if _needs_raw_bytes(opts):
            raw = _load_raw_bytes(state, opts)

        fmt = state.get("image_storage_format")

        if opts.read_dicom_header and raw and fmt == "dicom":
            _merge_missing(state, dicom_header_patches_from_bytes(raw))

        if (
            opts.read_image_header
            and raw
            and fmt in {"image/png", "image/jpeg"}
        ):
            _merge_missing(state, raster_image_header_patches_from_bytes(raw))

        if opts.compute_storage_hash and raw:
            patch_h: dict[str, Any] = {}
            if state.get("image_storage_hash") is None:
                patch_h["image_storage_hash"] = sha256_bytes(raw)
            _merge_missing(state, patch_h)

        if opts.compute_storage_checksum and raw:
            patch_c: dict[str, Any] = {}
            if state.get("image_storage_checksum") is None:
                patch_c["image_storage_checksum"] = md5_hex(raw)
            _merge_missing(state, patch_c)

        if opts.generate_thumbnails and raw and fmt is not None:
            if state.get("thumbnail_path") is None:
                pid = state.get("project_id")
                if pid is not None and fmt in {"dicom", "image/png", "image/jpeg"}:
                    tid = allocate_thumbnail_path(int(pid))
                    save_thumbnails_from_bytes(
                        raw,
                        image_storage_format=fmt,
                        thumbnail_path=tid,
                    )
                    _merge_missing(state, {"thumbnail_path": tid})

        prepared.append(ImportRow.model_validate(state))

    return prepared
