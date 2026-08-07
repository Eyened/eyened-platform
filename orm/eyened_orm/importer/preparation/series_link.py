from __future__ import annotations

from typing import Any

from eyened_orm.image_instance import Modality, ModalityType


def _is_oct_row(state: dict[str, Any]) -> bool:
    dm = state.get("dicom_modality")
    if dm is ModalityType.OPT or dm == ModalityType.OPT.value:
        return True
    modality = state.get("modality")
    if modality is Modality.OCT or modality == Modality.OCT.value:
        return True
    if modality is Modality.OCTA or modality == Modality.OCTA.value:
        return True
    return False


def _is_enface_candidate(state: dict[str, Any]) -> bool:
    if _is_oct_row(state):
        return False
    dm = state.get("dicom_modality")
    if dm is ModalityType.OP or dm == ModalityType.OP.value:
        return True
    modality = state.get("modality")
    if modality is None:
        return False
    name = getattr(modality, "value", str(modality)).upper()
    return any(tok in name for tok in ("INFRARED", "AUTOFLUORESCENCE", "FUNDUS", "REFLECTANCE"))


def _protected_from_series_rewrite(state: dict[str, Any]) -> bool:
    """Caller pinned an existing Series by PK; do not rewrite series_instance_uid."""
    return state.get("series_id") is not None


def link_oct_enface_series(states: list[dict[str, Any]]) -> int:
    """
    Co-locate each OPT/OCT volume with its enface localizer under one Series.

    Mutates ``states`` in place: sets enface (and other group members')
    ``series_instance_uid`` to the OCT row's ``series_instance_uid``.

    Linking prefers ``referenced_sop_instance_uids`` on the OCT row; falls back
    to shared ``frame_of_reference_uid`` among OCT + OP/enface candidates.

    Confirmed links (Referenced SOP or shared FrameOfReferenceUID) are applied
    even when ``series_anonymous_identity`` is set — otherwise distinct DICOM
    SeriesInstanceUIDs would keep the pair in separate Series. Rows with an
    explicit ``series_id`` are left alone.

    Returns the number of OCT–enface groups whose ``series_instance_uid`` was
    rewritten (0 if nothing changed).
    """
    by_sop: dict[str, list[int]] = {}
    for i, st in enumerate(states):
        sop = st.get("sop_instance_uid")
        if sop:
            by_sop.setdefault(str(sop), []).append(i)

    groups: list[set[int]] = []
    claimed: set[int] = set()

    for i, st in enumerate(states):
        if not _is_oct_row(st):
            continue
        if _protected_from_series_rewrite(st):
            continue

        members: set[int] = {i}
        refs = st.get("referenced_sop_instance_uids") or []
        for ref in refs:
            for j in by_sop.get(str(ref), []):
                if not _protected_from_series_rewrite(states[j]):
                    members.add(j)

        if len(members) == 1:
            # FoR fallback: pair with enface candidates sharing FrameOfReferenceUID
            for_uid = st.get("frame_of_reference_uid")
            if for_uid:
                for j, other in enumerate(states):
                    if j == i or j in claimed:
                        continue
                    if _protected_from_series_rewrite(other):
                        continue
                    if other.get("frame_of_reference_uid") != for_uid:
                        continue
                    if _is_enface_candidate(other):
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
        oct_indices = [k for k in members if _is_oct_row(states[k])]
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
