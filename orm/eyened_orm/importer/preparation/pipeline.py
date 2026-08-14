from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import AbstractSet, Any, Callable, Optional, Sequence

from eyened_orm.image_instance import Modality, ModalityType
from eyened_orm.importer.importer_dtos import ImportRow

from . import steps
from .dicom_meta import (
    DICOM_SERIES_LINKAGE_KEYS,
    LINK_META_KEYS,
    dicom_header_patches_from_bytes,
    strip_link_meta,
)
from .hashes import md5_hex, sha256_bytes
from .image_meta import raster_image_header_patches_from_bytes
from .series_link import SeriesLinkMeta, link_oct_enface_series, series_link_meta_from_patch
from .storage_io import try_read_storage_object_bytes

logger = logging.getLogger(__name__)


def _merge_missing(
    state: dict[str, Any],
    patch: dict[str, Any],
    *,
    skip: AbstractSet[str] | None = None,
) -> None:
    for k, v in patch.items():
        if v is None:
            continue
        if skip is not None and k in skip:
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
    infer_metadata_from_dicom_header: bool = False
    link_oct_enface_series: bool = False
    compute_storage_hash: bool = False
    compute_storage_checksum: bool = False
    raw_loader: Optional[Callable[[ImportRow], bytes | None]] = None


def _needs_raw_bytes(opts: PreparationOptions) -> bool:
    return (
        opts.infer_metadata_from_dicom_header
        or opts.link_oct_enface_series
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
    metas: Sequence[SeriesLinkMeta | None],
    *,
    dicom_rows: int,
    dicom_headers_read: int,
    linked_groups: int,
) -> None:
    """Warn when OCT–enface series linking is enabled but likely ineffective."""
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
            meta is not None
            and (
                _is_opt_dicom_modality(meta.dicom_modality)
                or meta.modality is Modality.OCT
                or meta.modality == Modality.OCT.value
            )
            for meta in metas
        )
        has_link_meta = any(
            meta is not None
            and (meta.referenced_sop_instance_uids or meta.frame_of_reference_uid)
            for meta in metas
        )
        if has_oct and not has_link_meta:
            logger.warning(
                "link_oct_enface_series=True but no FrameOfReferenceUID / "
                "ReferencedSOPInstanceUID metadata was found on prepared rows; "
                "OCT–enface series linking was a no-op."
            )


def _row_patch_from_dicom(
    patch: dict[str, Any],
    *,
    full_header: bool,
) -> dict[str, Any]:
    """Keep only ImportRow-bound keys; never include linker-only FoR/refs."""
    if full_header:
        return {k: v for k, v in patch.items() if k not in LINK_META_KEYS}
    return {k: v for k, v in patch.items() if k in DICOM_SERIES_LINKAGE_KEYS}


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

    Fields explicitly set on an ``ImportRow`` (including ``None``) are pinned and
    are never filled from ``defaults`` or DICOM/image header parsing.

    When ``link_oct_enface_series`` is True, OCT volumes and their referenced
    enface images are assigned a shared ``series_instance_uid`` so they land in
    one Series. Linking uses a parallel ``SeriesLinkMeta`` list (modality / FoR /
    refs) and does not require ``infer_metadata_from_dicom_header``.
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
    link_metas: list[SeriesLinkMeta | None] = []
    pinned_by_row: list[set[str]] = []
    dicom_rows = 0
    dicom_headers_read = 0
    parse_dicom = opts.infer_metadata_from_dicom_header or opts.link_oct_enface_series

    for row in rows:
        pinned = set(row.model_fields_set)
        state: dict[str, Any] = {**row.model_dump()}

        if opts.infer_image_format:
            r = ImportRow.model_validate(strip_link_meta(state))
            _merge_missing(
                state, steps.step_infer_image_storage_format(r), skip=pinned
            )

        _merge_missing(
            state,
            steps.step_apply_defaults(
                ImportRow.model_validate(strip_link_meta(state)), _defaults
            ),
            skip=pinned,
        )

        raw: bytes | None = None
        if _needs_raw_bytes(opts):
            raw = _load_raw_bytes(state, opts)

        fmt = state.get("image_storage_format")
        if fmt == "dicom":
            dicom_rows += 1

        link_meta: SeriesLinkMeta | None = None
        if parse_dicom and raw and fmt == "dicom":
            patch = dicom_header_patches_from_bytes(raw)
            link_meta = series_link_meta_from_patch(patch)
            row_patch = _row_patch_from_dicom(
                patch, full_header=opts.infer_metadata_from_dicom_header
            )
            _merge_missing(state, row_patch, skip=pinned)
            dicom_headers_read += 1

        if opts.read_image_header and raw and fmt in {"image/png", "image/jpeg"}:
            _merge_missing(
                state, raster_image_header_patches_from_bytes(raw), skip=pinned
            )

        if opts.compute_storage_hash and raw:
            patch_h: dict[str, Any] = {}
            if state.get("image_storage_hash") is None:
                patch_h["image_storage_hash"] = sha256_bytes(raw)
            _merge_missing(state, patch_h, skip=pinned)

        if opts.compute_storage_checksum and raw:
            patch_c: dict[str, Any] = {}
            if state.get("image_storage_checksum") is None:
                patch_c["image_storage_checksum"] = md5_hex(raw)
            _merge_missing(state, patch_c, skip=pinned)

        states.append(state)
        link_metas.append(link_meta)
        pinned_by_row.append(pinned)

    if opts.infer_metadata_from_dicom_header:
        _warn_modality_heuristics(states)

    linked_groups = 0
    if opts.link_oct_enface_series:
        linked_groups = link_oct_enface_series(
            states, link_metas, pinned_fields=pinned_by_row
        )
        _warn_series_link_limitations(
            link_metas,
            dicom_rows=dicom_rows,
            dicom_headers_read=dicom_headers_read,
            linked_groups=linked_groups,
        )

    return [ImportRow.model_validate(strip_link_meta(s)) for s in states]
