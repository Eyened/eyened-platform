from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from eyened_orm.image_instance import Modality, ModalityType


@dataclass(frozen=True)
class SeriesLinkMeta:
    """
    DICOM-derived metadata used only for OCT–enface series linking.

    Kept separate from ImportRow state so classification fields (modality) and
    linker-only UIDs never need to be merged into / stripped from the row.
    """

    sop_instance_uid: str | None = None
    frame_of_reference_uid: str | None = None
    referenced_sop_instance_uids: tuple[str, ...] = field(default_factory=tuple)
    dicom_modality: ModalityType | None = None
    modality: Modality | None = None


def series_link_meta_from_patch(patch: dict[str, Any]) -> SeriesLinkMeta:
    """Build linker metadata from a ``dicom_header_patches_from_bytes`` result."""
    refs = patch.get("referenced_sop_instance_uids") or ()
    if not isinstance(refs, tuple):
        refs = tuple(refs)
    return SeriesLinkMeta(
        sop_instance_uid=patch.get("sop_instance_uid"),
        frame_of_reference_uid=patch.get("frame_of_reference_uid"),
        referenced_sop_instance_uids=refs,
        dicom_modality=patch.get("dicom_modality"),
        modality=patch.get("modality"),
    )


def _is_oct_meta(meta: SeriesLinkMeta | None) -> bool:
    if meta is None:
        return False
    dm = meta.dicom_modality
    if dm is ModalityType.OPT or dm == ModalityType.OPT.value:
        return True
    modality = meta.modality
    if modality is Modality.OCT or modality == Modality.OCT.value:
        return True
    if modality is Modality.OCTA or modality == Modality.OCTA.value:
        return True
    return False


def _is_enface_meta(meta: SeriesLinkMeta | None) -> bool:
    if meta is None or _is_oct_meta(meta):
        return False
    dm = meta.dicom_modality
    if dm is ModalityType.OP or dm == ModalityType.OP.value:
        return True
    modality = meta.modality
    if modality is None:
        return False
    name = getattr(modality, "value", str(modality)).upper()
    return any(
        tok in name for tok in ("INFRARED", "AUTOFLUORESCENCE", "FUNDUS", "REFLECTANCE")
    )


def _protected_from_series_rewrite(state: dict[str, Any]) -> bool:
    """Caller pinned an existing Series by PK; do not rewrite series_instance_uid."""
    return state.get("series_id") is not None


def link_oct_enface_series(
    states: list[dict[str, Any]],
    metas: Sequence[SeriesLinkMeta | None],
) -> int:
    """
    Co-locate each OPT/OCT volume with its enface localizer under one Series.

    Mutates ``states`` in place: sets enface (and other group members')
    ``series_instance_uid`` to the OCT row's ``series_instance_uid``.

    Classification and FoR / Referenced SOP data come from ``metas`` (parallel to
    ``states``). Row state only supplies ``sop_instance_uid``,
    ``series_instance_uid``, and ``series_id``.

    Returns the number of OCT–enface groups whose ``series_instance_uid`` was
    rewritten (0 if nothing changed).
    """
    if len(metas) != len(states):
        raise ValueError(
            f"link_oct_enface_series: metas length {len(metas)} != states {len(states)}"
        )

    by_sop: dict[str, list[int]] = {}
    for i, st in enumerate(states):
        sop = st.get("sop_instance_uid")
        if sop is None and metas[i] is not None:
            sop = metas[i].sop_instance_uid
        if sop:
            by_sop.setdefault(str(sop), []).append(i)

    groups: list[set[int]] = []
    claimed: set[int] = set()

    for i, st in enumerate(states):
        meta = metas[i]
        if not _is_oct_meta(meta):
            continue
        if _protected_from_series_rewrite(st):
            continue

        members: set[int] = {i}
        refs = meta.referenced_sop_instance_uids if meta else ()
        for ref in refs:
            for j in by_sop.get(str(ref), []):
                if not _protected_from_series_rewrite(states[j]):
                    members.add(j)

        if len(members) == 1:
            for_uid = meta.frame_of_reference_uid if meta else None
            if for_uid:
                for j, other in enumerate(states):
                    if j == i or j in claimed:
                        continue
                    if _protected_from_series_rewrite(other):
                        continue
                    other_meta = metas[j]
                    if other_meta is None:
                        continue
                    if other_meta.frame_of_reference_uid != for_uid:
                        continue
                    if _is_enface_meta(other_meta):
                        members.add(j)

        if len(members) < 2:
            continue

        target = st.get("series_instance_uid")
        if target and all(
            states[k].get("series_instance_uid") == target for k in members
        ):
            claimed.update(members)
            continue

        groups.append(members)
        claimed.update(members)

    rewritten = 0
    for members in groups:
        oct_indices = [k for k in members if _is_oct_meta(metas[k])]
        target_uid = None
        for k in oct_indices:
            target_uid = states[k].get("series_instance_uid")
            if target_uid:
                break
        if not target_uid:
            for k in members:
                target_uid = states[k].get("series_instance_uid")
                if target_uid:
                    break
        if not target_uid:
            continue

        if all(states[k].get("series_instance_uid") == target_uid for k in members):
            continue

        for k in members:
            if _protected_from_series_rewrite(states[k]):
                continue
            states[k]["series_instance_uid"] = target_uid
        rewritten += 1

    return rewritten
