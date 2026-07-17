"""The six EXISTS (semi-join) builders for the search surfaces.

Moved verbatim from the old route module. Carries two known query-shape
inefficiencies unchanged (the attribute-def N+1 in ``exists_attributes_for_instance``
and its OR-of-joins EXISTS); those are gated follow-up work, not to be "fixed"
here. Each builder takes an entity->conditions grouping and returns an EXISTS
clause (or None when the group is empty).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from eyened_orm import (
    Feature,
    FormAnnotationTagLink,
    FormSchema,
    ImageInstance,
    ImageInstanceTagLink,
    Segmentation,
    SegmentationTagLink,
    Study,
    StudyTagLink,
)
from eyened_orm.attributes import AttributeDefinition as AttrDef
from eyened_orm.attributes import AttributeValue as AttrVal
from eyened_orm.attributes import AttributesModel, AttributesModelOutput
from eyened_orm.segmentation import ModelSegmentation, SegmentationModel
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

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
from .conditions import and_expr, format_attr_condition_with_definition


def exists_forms_for_study(forms_group: Dict[Any, List[Dict[str, Any]]]) -> Any:
    """EXISTS subquery for forms correlated by Study."""
    if not any(forms_group.values()):
        return None

    subq = (
        select(1)
        .select_from(ActiveFormAnnotation)
        .where(ActiveFormAnnotation.StudyID == Study.StudyID)
    )

    if FormSchema in forms_group:
        subq = subq.join(
            FormSchema,
            ActiveFormAnnotation.FormSchemaID == FormSchema.FormSchemaID,
            isouter=True,
        )
    if FormCreator in forms_group:
        subq = subq.join(
            FormCreator,
            ActiveFormAnnotation.CreatorID == FormCreator.CreatorID,
            isouter=True,
        )
    if FormTag in forms_group:
        subq = subq.join(
            FormAnnotationTagLink,
            ActiveFormAnnotation.FormAnnotationID
            == FormAnnotationTagLink.FormAnnotationID,
            isouter=True,
        ).join(
            FormTag,
            FormAnnotationTagLink.TagID == FormTag.TagID,
            isouter=True,
        )

    subconds: List[Dict[str, Any]] = []
    for conds in forms_group.values():
        subconds.extend(conds)
    if subconds:
        subq = subq.where(and_expr(subconds))

    return subq.exists()


def exists_forms_for_instance(forms_group: Dict[Any, List[Dict[str, Any]]]) -> Any:
    """EXISTS subquery for forms correlated by ImageInstance."""
    if not any(forms_group.values()):
        return None

    subq = (
        select(1)
        .select_from(ActiveFormAnnotation)
        .where(ActiveFormAnnotation.ImageInstanceID == ImageInstance.ImageInstanceID)
    )

    if FormSchema in forms_group:
        subq = subq.join(
            FormSchema,
            ActiveFormAnnotation.FormSchemaID == FormSchema.FormSchemaID,
            isouter=True,
        )
    if FormCreator in forms_group:
        subq = subq.join(
            FormCreator,
            ActiveFormAnnotation.CreatorID == FormCreator.CreatorID,
            isouter=True,
        )
    if FormTag in forms_group:
        subq = subq.join(
            FormAnnotationTagLink,
            ActiveFormAnnotation.FormAnnotationID
            == FormAnnotationTagLink.FormAnnotationID,
            isouter=True,
        ).join(
            FormTag,
            FormAnnotationTagLink.TagID == FormTag.TagID,
            isouter=True,
        )

    subconds: List[Dict[str, Any]] = []
    for conds in forms_group.values():
        subconds.extend(conds)
    if subconds:
        subq = subq.where(and_expr(subconds))

    return subq.exists()


def exists_segs_for_instance(segs_group: Dict[Any, List[Dict[str, Any]]]) -> Any:
    """EXISTS subquery for segmentations correlated by ImageInstance."""
    if not any(segs_group.values()):
        return None

    subq = (
        select(1)
        .select_from(ActiveSegmentation)
        .where(ActiveSegmentation.ImageInstanceID == ImageInstance.ImageInstanceID)
    )

    if Feature in segs_group:
        subq = subq.join(
            Feature,
            ActiveSegmentation.FeatureID == Feature.FeatureID,
            isouter=True,
        )
    if SegCreator in segs_group:
        subq = subq.join(
            SegCreator,
            ActiveSegmentation.CreatorID == SegCreator.CreatorID,
            isouter=True,
        )
    if SegTag in segs_group:
        subq = subq.join(
            SegmentationTagLink,
            ActiveSegmentation.SegmentationID == SegmentationTagLink.SegmentationID,
            isouter=True,
        ).join(
            SegTag,
            SegmentationTagLink.TagID == SegTag.TagID,
            isouter=True,
        )

    subconds: List[Dict[str, Any]] = []
    for conds in segs_group.values():
        subconds.extend(conds)
    if subconds:
        subq = subq.where(and_expr(subconds))

    return subq.exists()


def exists_inst_tags_for_instance(tags_group: Dict[Any, List[Dict[str, Any]]]) -> Any:
    """EXISTS subquery for image tags correlated by ImageInstance."""
    if InstTag not in tags_group:
        return None

    subq = (
        select(1)
        .select_from(ImageInstanceTagLink)
        .where(ImageInstanceTagLink.ImageInstanceID == ImageInstance.ImageInstanceID)
        .join(InstTag, ImageInstanceTagLink.TagID == InstTag.TagID, isouter=True)
    )

    subq = subq.where(and_expr(tags_group[InstTag]))
    return subq.exists()


def exists_study_tags_for_study(tags_group: Dict[Any, List[Dict[str, Any]]]) -> Any:
    """EXISTS subquery for study tags correlated by Study."""
    if StudyTag not in tags_group:
        return None
    subq = (
        select(1)
        .select_from(StudyTagLink)
        .where(StudyTagLink.StudyID == Study.StudyID)
        .join(StudyTag, StudyTagLink.TagID == StudyTag.TagID, isouter=True)
    )
    subq = subq.where(and_expr(tags_group[StudyTag]))
    return subq.exists()


def resolve_attribute_definitions(
    session: Session,
    keys: List[Tuple[Optional[str], str, Optional[str]]],
) -> Dict[Tuple[Optional[str], str, Optional[str]], AttrDef]:
    """Resolve each unique (model, attr, feature) key to its AttributeDefinition.

    One query per unique key -- the attribute-def N+1, preserved verbatim as gated
    follow-up work. A key whose definition does not resolve is simply absent from
    the returned dict; callers decide whether that is a skip or a hard error. The
    lookup keys on model+attr only; feature is carried in the key but filtered
    later in the EXISTS subquery, exactly as before.
    """
    attr_defs: Dict[Tuple[Optional[str], str, Optional[str]], AttrDef] = {}
    for model_name, attr_name, feature_name in dict.fromkeys(keys):
        if model_name:
            # DISTINCT because Model allows several Versions per ModelName (see
            # migration 2026_06_30-fix_model_unique_constraints): the output join
            # returns one row per version, all of them the same AttributeDefinition.
            # AttributeName is uniquely constrained, so collapsing them is lossless
            # and scalar_one_or_none still guards a real invariant break.
            attr_def_stmt = (
                select(AttrDef)
                .join(
                    AttributesModelOutput,
                    AttrDef.AttributeID == AttributesModelOutput.AttributeID,
                )
                .join(
                    AttributesModel,
                    AttributesModelOutput.ModelID == AttributesModel.ModelID,
                )
                .where(AttributesModel.ModelName == model_name)
                .where(AttrDef.AttributeName == attr_name)
                .distinct()
            )
        else:
            attr_def_stmt = select(AttrDef).where(AttrDef.AttributeName == attr_name)

        attr_def = session.execute(attr_def_stmt).scalar_one_or_none()

        if not attr_def:
            continue

        attr_defs[(model_name, attr_name, feature_name)] = attr_def
    return attr_defs


def exists_attributes_for_instance(
    attr_conds: List[Tuple[Optional[str], str, Optional[str], Dict[str, Any]]],
    attr_defs: Dict[Tuple[Optional[str], str, Optional[str]], AttrDef],
) -> Any:
    """EXISTS subqueries for attributes correlated by ImageInstance.

    Takes the already-resolved definitions rather than resolving them: the caller
    resolves once per request and hands the map to both the search and the count,
    which used to rebuild (and re-resolve) it independently. An unresolved key is
    still skipped here -- the service rejects it upstream with a 400.
    """
    if not attr_conds:
        return None

    and_predicates = []

    for model_name, attr_name, feature_name, c in attr_conds:
        attr_def = attr_defs.get((model_name, attr_name, feature_name))
        if not attr_def:
            continue

        subq = (
            select(1)
            .select_from(AttrVal)
            .join(AttrDef, AttrVal.AttributeID == AttrDef.AttributeID)
        )

        if model_name:
            subq = subq.join(
                AttributesModel, AttrVal.ModelID == AttributesModel.ModelID
            )

        # Outer joins to entities
        subq = subq.outerjoin(
            Segmentation, AttrVal.SegmentationID == Segmentation.SegmentationID
        ).outerjoin(
            ModelSegmentation,
            AttrVal.ModelSegmentationID == ModelSegmentation.ModelSegmentationID,
        )

        if model_name:
            # ROBUST: Join SegmentationModel early to get its Feature
            subq = subq.outerjoin(
                SegmentationModel,
                ModelSegmentation.ModelID == SegmentationModel.ModelID,
            )
        elif feature_name:
            # If no model filter, but feature filter exists, we still need SegmentationModel for ModelSegmentation path
            subq = subq.outerjoin(
                SegmentationModel,
                ModelSegmentation.ModelID == SegmentationModel.ModelID,
            )

        subq = subq.where(
            # Match if ANY of the three paths lead to this ImageInstance
            or_(
                AttrVal.ImageInstanceID == ImageInstance.ImageInstanceID,
                Segmentation.ImageInstanceID == ImageInstance.ImageInstanceID,
                ModelSegmentation.ImageInstanceID == ImageInstance.ImageInstanceID,
            )
        )

        if model_name:
            subq = subq.where(AttributesModel.ModelName == model_name)
        else:
            subq = subq.where(AttrVal.ModelID.is_(None))

        subq = subq.where(AttrDef.AttributeName == attr_name)
        subq = subq.where(format_attr_condition_with_definition(attr_def, c))

        # Feature filter
        if feature_name:
            subq = subq.outerjoin(
                Feature,
                or_(
                    Segmentation.FeatureID == Feature.FeatureID,
                    SegmentationModel.FeatureID == Feature.FeatureID,
                ),
            ).where(Feature.FeatureName == feature_name)

        and_predicates.append(subq.exists())

    return and_(*and_predicates) if and_predicates else None
