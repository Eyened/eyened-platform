from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from eyened_orm.image_instance import Modality, ModalityType
from eyened_orm.importer.importer_dtos import ImportRow

from . import steps
from .dicom_meta import dicom_header_patches_from_bytes, strip_link_meta
from .hashes import md5_hex, sha256_bytes
from .image_meta import raster_image_header_patches_from_bytes
from .series_link import link_oct_enface_series
from .storage_io import try_read_storage_object_bytes

logger = logging.getLogger(__name__)


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
    link_oct_enface_series: bool = False
    compute_storage_hash: bool = False
    compute_storage_checksum: bool = False
    raw_loader: Optional[Callable[[ImportRow], bytes | None]] = None


def _needs_raw_bytes(opts: PreparationOptions) -> bool:
    return (
        opts.read_dicom_header
        or opts.read_image_header
        or opts.compute_storage_hash
        or opts.compute_storage_checksum
    )


def _load_raw_bytes(state: dict[str, Any], opts: PreparationOptions) -> bytes | None:
    row = ImportRow.model_validate(strip_link_meta(state))
    if opts.raw_loader is not None:
        return opts.raw_loader(row)
    return try_read_storage_object_bytes(
        state.get("storage_backend_key"), state.get("object_key")
    )


def _is_opt_dicom_modality(val: Any) -> bool:
    return val is ModalityType.OPT or val == ModalityType.OPT.value


def _is_op_dicom_modality(val: Any) -> bool:
    return val is ModalityType.OP or val == ModalityType.OP.value


def _warn_modality_heuristics(states: list[dict[str, Any]]) -> None:
    """Warn about Spectralis-oriented OPT/OP → viewer-modality mapping limits."""
    opt_as_oct = 0
    op_without_viewer_modality = 0
    for st in states:
        if st.get("modality") is Modality.OCT and _is_opt_dicom_modality(
            st.get("dicom_modality")
        ):
            opt_as_oct += 1
        if _is_op_dicom_modality(st.get("dicom_modality")) and st.get("modality") is None:
            op_without_viewer_modality += 1

    if opt_as_oct:
        logger.warning(
            "Mapped %d DICOM OPT volume(s) to viewer modality OCT. "
            "OCTA is not inferred automatically; set modality explicitly if needed.",
            opt_as_oct,
        )
    if op_without_viewer_modality:
        logger.warning(
            "Left viewer modality unset for %d DICOM OP image(s) without a recognized "
            "ImageType subtype (RED→InfraredReflectance, AF→Autofluorescence). "
            "Set modality explicitly if needed.",
            op_without_viewer_modality,
        )


def _warn_series_link_limitations(
    opts: PreparationOptions,
    states: list[dict[str, Any]],
    *,
    dicom_rows: int,
    dicom_headers_read: int,
    linked_groups: int,
) -> None:
    """Warn when OCT–enface series linking is enabled but likely ineffective."""
    if not opts.read_dicom_header:
        logger.warning(
            "link_oct_enface_series=True but read_dicom_header=False; "
            "linking needs DICOM FrameOfReferenceUID / ReferencedSOPInstanceUID "
            "from header parsing and will be a no-op."
        )
        return

    if dicom_rows and dicom_headers_read == 0:
        logger.warning(
            "link_oct_enface_series=True but no DICOM headers were read for %d "
            "dicom row(s). Check EYENED_STORAGE_MOUNTS + relative object_key "
            "(or pass PreparationOptions.raw_loader); series linking will be a no-op.",
            dicom_rows,
        )
        return

    if dicom_rows and dicom_headers_read < dicom_rows:
        logger.warning(
            "link_oct_enface_series=True but only %d/%d dicom row(s) had readable "
            "headers; the rest could not be linked from DICOM metadata.",
            dicom_headers_read,
            dicom_rows,
        )

    if linked_groups == 0 and dicom_headers_read > 0:
        has_oct = any(
            _is_opt_dicom_modality(st.get("dicom_modality"))
            or st.get("modality") is Modality.OCT
            or st.get("modality") == Modality.OCT.value
            for st in states
        )
        has_link_meta = any(
            st.get("referenced_sop_instance_uids") or st.get("frame_of_reference_uid")
            for st in states
        )
        if has_oct and not has_link_meta:
            logger.warning(
                "link_oct_enface_series=True but no FrameOfReferenceUID / "
                "ReferencedSOPInstanceUID metadata was found on prepared rows; "
                "OCT–enface series linking was a no-op."
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
    ``object_key``), or via ``PreparationOptions.raw_loader``.

    When ``link_oct_enface_series`` is True (typically with ``read_dicom_header``),
    OCT volumes and their referenced enface images are assigned a shared
    ``series_instance_uid`` so they land in one Series.
    """
    if options is None:
        opts = PreparationOptions(
            infer_image_format=infer_image_format,
            defaults=defaults,
        )
    else:
        opts = options

    _defaults = opts.defaults or {}
    states: list[dict[str, Any]] = []
    dicom_rows = 0
    dicom_headers_read = 0

    for row in rows:
        state: dict[str, Any] = {**row.model_dump()}

        if opts.infer_image_format:
            r = ImportRow.model_validate(strip_link_meta(state))
            _merge_missing(state, steps.step_infer_image_storage_format(r))

        _merge_missing(
            state,
            steps.step_apply_defaults(
                ImportRow.model_validate(strip_link_meta(state)), _defaults
            ),
        )

        raw: bytes | None = None
        if _needs_raw_bytes(opts):
            raw = _load_raw_bytes(state, opts)

        fmt = state.get("image_storage_format")
        if fmt == "dicom":
            dicom_rows += 1

        if opts.read_dicom_header and raw and fmt == "dicom":
            _merge_missing(state, dicom_header_patches_from_bytes(raw))
            dicom_headers_read += 1

        if opts.read_image_header and raw and fmt in {"image/png", "image/jpeg"}:
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

        states.append(state)

    if opts.read_dicom_header:
        _warn_modality_heuristics(states)

    linked_groups = 0
    if opts.link_oct_enface_series:
        linked_groups = link_oct_enface_series(states)
        _warn_series_link_limitations(
            opts,
            states,
            dicom_rows=dicom_rows,
            dicom_headers_read=dicom_headers_read,
            linked_groups=linked_groups,
        )

    return [ImportRow.model_validate(strip_link_meta(s)) for s in states]
