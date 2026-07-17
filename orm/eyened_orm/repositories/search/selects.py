"""Base SELECT construction and the eager-load option-sets for search.

``*_filtered_select`` reproduce the old route module's ``_build_instance_select``
/ ``_build_study_select`` WHERE construction verbatim, differing only in that they
receive already-resolved conditions (as the typed carriers) and no longer resolve
UI labels -- that now happens in the service. The typed carriers are converted to
the plain-dict shape the moved machinery expects right at the top of each builder,
so the partitioning and EXISTS assembly below are byte-for-byte unchanged. Ordering
is split out (``build_*_select``) so the count path can reuse the same predicate
without an ORDER BY it does not need.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from eyened_orm import (
    DeviceInstance,
    DeviceModel,
    Feature,
    FormSchema,
    ImageInstance,
    ImageInstanceTagLink,
    ImageStorage,
    Patient,
    Project,
    Scan,
    Series,
    SourceInfo,
    Study,
)
from eyened_orm.attributes import AttributeValue as AttrVal
from sqlalchemy import and_, select, true
from sqlalchemy.orm import selectinload

from .aliases import (
    ActiveFormAnnotation,
    ActiveSegmentation,
    FormCreator,
    FormTag,
    InstTag,
    SegCreator,
    SegTag,
    StudyTag,
)
from eyened_orm.attributes import AttributeDefinition as AttrDef

from .conditions import (
    AttributeConditionSpec,
    ResolvedCondition,
    and_expr,
    partition_conditions_by_entity,
)
from .exists import (
    exists_attributes_for_instance,
    exists_forms_for_instance,
    exists_forms_for_study,
    exists_inst_tags_for_instance,
    exists_segs_for_instance,
    exists_study_tags_for_study,
)


def instance_options() -> list[Any]:
    """Eager-load option-set shared by every ImageInstance result."""
    return [
        selectinload(ImageInstance.Series)
        .selectinload(Series.Study)
        .selectinload(Study.Patient)
        .selectinload(Patient.Project),
        selectinload(ImageInstance.DeviceInstance).selectinload(
            DeviceInstance.DeviceModel
        ),
        selectinload(ImageInstance.SourceInfo),
        selectinload(ImageInstance.Scan),
        selectinload(ImageInstance.ImageStorages).selectinload(
            ImageStorage.StorageBackend
        ),
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(
            ImageInstanceTagLink.Tag
        ),
        # attributes
        selectinload(ImageInstance.AttributeValues).selectinload(
            AttrVal.AttributeDefinition
        ),
        selectinload(ImageInstance.AttributeValues).selectinload(
            AttrVal.ProducingModel
        ),
    ]


def study_options() -> list[Any]:
    """Eager-load option-set for a Study result and its active instances."""
    return [
        selectinload(Study.Series).selectinload(
            Series.ImageInstances.and_(~ImageInstance.Inactive)
        )
    ]


def _as_dict(condition: ResolvedCondition) -> Dict[str, Any]:
    """Adapt a typed condition to the plain-dict shape the moved machinery reads."""
    return {
        "variable": condition.variable,
        "operator": condition.operator,
        "value": condition.value,
    }


def _attr_tuples(
    attr_conditions: Sequence[AttributeConditionSpec],
) -> List[tuple]:
    """Adapt attribute specs to the (model, attr, feature, cond-dict) tuples."""
    return [
        (
            spec.model,
            spec.attribute,
            spec.feature,
            {"operator": spec.operator, "value": spec.value},
        )
        for spec in attr_conditions
    ]


def instance_filtered_select(
    conditions: Sequence[ResolvedCondition],
    attr_conditions: Sequence[AttributeConditionSpec],
    attr_defs: Dict[Tuple[Optional[str], str, Optional[str]], AttrDef],
):
    """Build the filtered ImageInstance select (base + all EXISTS), without ordering."""
    static_dicts = [_as_dict(c) for c in conditions]
    attr_conds_raw = _attr_tuples(attr_conditions)

    by_entity = partition_conditions_by_entity(static_dicts)

    base_entities = {
        ImageInstance,
        Series,
        Study,
        Patient,
        Project,
        DeviceInstance,
        DeviceModel,
        SourceInfo,
        Scan,
    }
    base_conds: List[Dict[str, Any]] = []
    seg_group: Dict[Any, List[Dict[str, Any]]] = {}
    form_group: Dict[Any, List[Dict[str, Any]]] = {}
    img_tag_group: Dict[Any, List[Dict[str, Any]]] = {}

    for ent, conds in by_entity.items():
        if ent in base_entities:
            base_conds.extend(conds)
        elif ent in {ActiveSegmentation, Feature, SegCreator, SegTag}:
            seg_group[ent] = conds
        elif ent in {ActiveFormAnnotation, FormSchema, FormCreator, FormTag}:
            form_group[ent] = conds
        elif ent in {InstTag}:
            img_tag_group[ent] = conds

    q = (
        select(ImageInstance)
        .filter(~ImageInstance.Inactive)
        .join_from(
            ImageInstance,
            Series,
            ImageInstance.SeriesID == Series.SeriesID,
            isouter=True,
        )
        .join_from(Series, Study, isouter=True)
        .join_from(Study, Patient, isouter=True)
        .join_from(Patient, Project, isouter=True)
        .join_from(ImageInstance, DeviceInstance, isouter=True)
        .join_from(DeviceInstance, DeviceModel, isouter=True)
        .join_from(ImageInstance, SourceInfo, isouter=True)
        .join_from(ImageInstance, Scan, isouter=True)
    )

    and_predicates: List[Any] = []
    if base_conds:
        and_predicates.append(and_expr(base_conds))

    seg_exists = exists_segs_for_instance(seg_group)
    if seg_exists is not None:
        and_predicates.append(seg_exists)
    form_exists = exists_forms_for_instance(form_group)
    if form_exists is not None:
        and_predicates.append(form_exists)
    tag_exists = exists_inst_tags_for_instance(img_tag_group)
    if tag_exists is not None:
        and_predicates.append(tag_exists)

    # Attribute EXISTS filters
    attr_exists = exists_attributes_for_instance(attr_conds_raw, attr_defs)
    if attr_exists is not None:
        and_predicates.append(attr_exists)

    where_clause = and_(*and_predicates) if and_predicates else true()
    return q.where(where_clause)


def build_instance_select(
    conditions: Sequence[ResolvedCondition],
    attr_conditions: Sequence[AttributeConditionSpec],
    attr_defs: Dict[Tuple[Optional[str], str, Optional[str]], AttrDef],
    order_by: Any,
    order: str,
):
    """The filtered instance select plus ordering (resolved order column + PK tiebreaker)."""
    q = instance_filtered_select(conditions, attr_conditions, attr_defs)
    sort_dir = order_by.asc() if order == "ASC" else order_by.desc()
    return q.order_by(sort_dir, ImageInstance.ImageInstanceID.asc())


def study_filtered_select(conditions: Sequence[ResolvedCondition]):
    """Build the filtered Study select (base + forms/study-tag EXISTS), without ordering."""
    static_dicts = [_as_dict(c) for c in conditions]
    by_entity = partition_conditions_by_entity(static_dicts)

    base_entities = {Study, Patient, Project}
    base_conds: List[Dict[str, Any]] = []
    form_group: Dict[Any, List[Dict[str, Any]]] = {}
    study_tag_group: Dict[Any, List[Dict[str, Any]]] = {}

    for ent, conds in by_entity.items():
        if ent in base_entities:
            base_conds.extend(conds)
        elif ent in {ActiveFormAnnotation, FormSchema, FormCreator, FormTag}:
            form_group[ent] = conds
        elif ent in {StudyTag}:
            study_tag_group[ent] = conds

    q = (
        select(Study)
        .join_from(Study, Patient, onclause=Study.PatientID == Patient.PatientID)
        .join_from(Patient, Project)
    )

    and_predicates: List[Any] = []
    if base_conds:
        and_predicates.append(and_expr(base_conds))

    forms_exists = exists_forms_for_study(form_group)
    if forms_exists is not None:
        and_predicates.append(forms_exists)

    study_tags_exists = exists_study_tags_for_study(study_tag_group)
    if study_tags_exists is not None:
        and_predicates.append(study_tags_exists)

    where_clause = and_(*and_predicates) if and_predicates else true()
    return q.where(where_clause)


def build_study_select(
    conditions: Sequence[ResolvedCondition],
    order_by: Any,
    order: str,
):
    """The filtered study select plus ordering (resolved order column + PK tiebreaker)."""
    q = study_filtered_select(conditions)
    sort_dir = order_by.asc() if order == "ASC" else order_by.desc()
    # Add deterministic tiebreaker
    return q.order_by(sort_dir, Study.StudyID.asc())
