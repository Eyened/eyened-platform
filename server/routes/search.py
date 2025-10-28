from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Literal, Optional, Union, Tuple, cast, Annotated

from eyened_orm import (
    DeviceModel,
    DeviceInstance,
    Feature,
    FormAnnotation,
    FormAnnotationTagLink,
    ImageInstance,
    ImageInstanceTagLink,
    Patient,
    Project,
    Scan,
    Series,
    SourceInfo,
    Study,
    FormSchema,
    Tag,
    Annotation,
    StudyTagLink,
    Creator,
    Segmentation,
    SegmentationTagLink,
)
from eyened_orm.attributes import AttributeDefinition as AttrDef, AttributeValue as AttrVal, AttributeDataType, AttributesModelOutput
from eyened_orm.segmentation import ModelSegmentation, SegmentationModel
from eyened_orm.attributes import AttributesModel
from eyened_orm.image_instance import Laterality as ImgLaterality, Modality as ImgModality, ETDRSField as ImgETDRS
from eyened_orm.patient import SexEnum as PatientSex
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from sqlalchemy import select, func, and_, or_, true, union_all, literal
from sqlalchemy.orm import Session, aliased, selectinload
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import mysql

from .auth import CurrentUser, get_current_user
from ..db import get_db
from ..dtos import InstanceGET, StudyGET, InstanceMeta
from ..dtos.dto_converter import DTOConverter

router = APIRouter()

ActiveSegmentation = aliased(
    Segmentation,
    select(Segmentation).filter(~Segmentation.Inactive).subquery(name="active_segmentation"),
    name="active_segmentation",
)
ActiveFormAnnotation = aliased(
    FormAnnotation,
    select(FormAnnotation).filter(~FormAnnotation.Inactive).subquery(name="active_form_annot"),
    name="active_form_annot",
)
SegCreator = aliased(Creator, name="seg_creator")
FormCreator = aliased(Creator, name="form_creator")
SegTag = aliased(Tag, name="seg_tag")
FormTag = aliased(Tag, name="form_tag")
InstTag = aliased(Tag, name="image_tag")
StudyTag = aliased(Tag, name="study_tag")

# list of properties that are searchable with identifier and mapped ORM property
searchable_fields = Literal[
    'Image DBID',
    'Laterality',
    'Modality',
    'ETDRS Field',
    'Color Fundus Quality',
    'Study Date',
    'Patient Identifier',
    'Patient Sex',
    'Patient Birthdate',
    'Project Name',
    'Device Model ID',

    'Segmentation Feature Name',  # backward-compat
    'Segmentation Creator Name',
    'Segmentation Tag Name',
    'Form Schema Name',
    'Form Creator Name',
    'Form Tag Name',
    'Image Tag Name',
]

operators = Literal[">", "<", ">=", "<=", "==", "!=", "IN"]

instance_search_fields_map: Dict[searchable_fields, Any] = {
    'Image DBID': ImageInstance.ImageInstanceID,
    'Laterality': ImageInstance.Laterality,
    'Modality': ImageInstance.Modality,
    'ETDRS Field': ImageInstance.ETDRSField,
    'Color Fundus Quality': ImageInstance.CFQuality,
    'Study Date': Study.StudyDate,
    'Patient Identifier': Patient.PatientIdentifier,
    'Patient Sex': Patient.Sex,
    'Patient Birthdate': Patient.BirthDate,
    'Project Name': Project.ProjectName,
    'Device Model ID': DeviceModel.DeviceModelID,

    'Segmentation Feature Name': Feature.FeatureName,
    'Segmentation Creator Name': SegCreator.CreatorName,
    'Segmentation Tag Name': SegTag.TagName,
    'Form Schema Name': FormSchema.SchemaName,
    'Form Creator Name': FormCreator.CreatorName,
    'Form Tag Name': FormTag.TagName,
    'Image Tag Name': InstTag.TagName,
}

# Study search
study_searchable_fields = Literal[
    'Study Date',
    'Study Description',
    'Study Round',
    'Patient Identifier',
    'Patient Sex',
    'Patient Birthdate',
    'Project Name',
    'Form Schema Name',
    'Form Creator Name',
    'Form Tag Name',
    'Study Tag Name',
]

study_search_fields_map: Dict[study_searchable_fields, Any] = {
    'Study Date': Study.StudyDate,
    'Study Description': Study.StudyDescription,
    'Study Round': Study.StudyRound,
    'Patient Identifier': Patient.PatientIdentifier,
    'Patient Sex': Patient.Sex,
    'Patient Birthdate': Patient.BirthDate,
    'Project Name': Project.ProjectName,
    'Form Schema Name': FormSchema.SchemaName,
    'Form Creator Name': FormCreator.CreatorName,
    'Form Tag Name': FormTag.TagName,
    'Study Tag Name': StudyTag.TagName,
}

# Order-by options for instances
instance_order_by_fields = Literal[
    'Study Date',
    'Patient Birthdate',
    'Date Inserted',
]

instance_order_by_fields_map: Dict[instance_order_by_fields, Any] = {
    'Study Date': Study.StudyDate,
    'Patient Birthdate': Patient.BirthDate,
    'Date Inserted': ImageInstance.DateInserted,
}

# Order-by options for studies
study_order_by_fields = Literal[
    'Study Date',
    'Patient Birthdate',
    'Date Inserted',
]

study_order_by_fields_map: Dict[study_order_by_fields, Any] = {
    'Study Date': Study.StudyDate,
    'Patient Birthdate': Patient.BirthDate,
    'Date Inserted': Study.DateInserted,
}


def _map_mysql_operator(operator: str, value: Any) -> str:
    """Map user-provided operator to a MySQL-valid operator, considering NULL semantics."""
    if operator == "==":
        return "IS" if value is None else "="
    if operator == "!=":
        return "IS NOT" if value is None else "!="
    return operator


def format_condition(variable: Any, condition: Dict[str, Any]) -> Any:
    """Return a SQLAlchemy boolean expression for one condition."""
    op = condition["operator"]
    value = condition["value"]

    if value is None:
        return variable.is_(None) if op == "==" else variable.is_not(None)
    if isinstance(value, list):
        return variable.in_(value)
    if op == "==":
        return variable == value
    if op == "!=":
        return variable != value
    if op == ">":
        return variable > value
    if op == "<":
        return variable < value
    if op == ">=":
        return variable >= value
    if op == "<=":
        return variable <= value
    raise ValueError(f"Unsupported operator: {op}")


def create_condition(conditions: List[Dict[str, Any]], fields_map: Optional[Dict[str, Any]] = None) -> Any:
    """Build a SQLAlchemy boolean expression from user conditions."""
    if fields_map is None:
        fields_map = instance_search_fields_map

    # Map variables to ORM attributes
    for c in conditions:
        assert c["variable"] in fields_map, f"Invalid variable: {c['variable']}"
        c["variable"] = fields_map[c["variable"]]

    # OR all conditions globally (no per-variable grouping)
    exprs: List[Any] = [format_condition(c["variable"], c) for c in conditions]
    return or_(*exprs) if exprs else true()
ATTRIBUTE_VAR_RE = r"^(?P<model>[^\[]+)\[(?P<attr>[^\]]+)\]$"

def parse_attribute_var(name: str) -> Optional[Tuple[str, str]]:
    import re
    m = re.match(ATTRIBUTE_VAR_RE, name)
    if not m:
        return None
    return m.group("model"), m.group("attr")

def get_value_column_for_attribute(attr_def: AttrDef) -> Any:
    """Get the correct value column based on the attribute's data type."""
    if attr_def.AttributeDataType == AttributeDataType.Int:
        return AttrVal.ValueInt
    elif attr_def.AttributeDataType == AttributeDataType.Float:
        return AttrVal.ValueFloat
    elif attr_def.AttributeDataType == AttributeDataType.String:
        return AttrVal.ValueText
    elif attr_def.AttributeDataType == AttributeDataType.JSON:
        return AttrVal.ValueJSON
    else:
        # Fallback to text for unknown types
        return AttrVal.ValueText

def convert_search_value_to_attribute_type(value: Any, attr_def: AttrDef) -> Any:
    """Convert search value to match the attribute's data type."""
    if value is None:
        return None
    
    # Handle list values (for IN operations)
    if isinstance(value, list):
        try:
            if attr_def.AttributeDataType == AttributeDataType.Int:
                return [int(v) if not isinstance(v, bool) else (1 if v else 0) for v in value]
            elif attr_def.AttributeDataType == AttributeDataType.Float:
                return [float(v) for v in value]
            elif attr_def.AttributeDataType == AttributeDataType.String:
                return [str(v) for v in value]
            elif attr_def.AttributeDataType == AttributeDataType.JSON:
                return value  # Keep as-is for JSON
            else:
                return [str(v) for v in value]
        except (ValueError, TypeError):
            # If conversion fails, return as string list for text comparison
            return [str(v) for v in value]
    
    # Handle single values
    try:
        if attr_def.AttributeDataType == AttributeDataType.Int:
            return int(value) if not isinstance(value, bool) else (1 if value else 0)
        elif attr_def.AttributeDataType == AttributeDataType.Float:
            return float(value)
        elif attr_def.AttributeDataType == AttributeDataType.String:
            return str(value)
        elif attr_def.AttributeDataType == AttributeDataType.JSON:
            # For JSON, we might need special handling
            return value
        else:
            return str(value)
    except (ValueError, TypeError):
        # If conversion fails, return as string for text comparison
        return str(value)

def format_attr_condition_with_definition(attr_def: AttrDef, condition: Dict[str, Any]) -> Any:
    """Format attribute condition using the correct value column based on attribute definition."""
    value_column = get_value_column_for_attribute(attr_def)
    converted_value = convert_search_value_to_attribute_type(condition["value"], attr_def)
    
    # Create a new condition with the converted value
    converted_condition = {**condition, "value": converted_value}
    return format_condition(value_column, converted_condition)

def format_attr_condition(value_column: Any, condition: Dict[str, Any]) -> Any:
    """Legacy function - use format_attr_condition_with_definition instead."""
    cond = {**condition, "variable": value_column}
    return format_condition(value_column, cond)


# ----------------------------------------
# Helpers for EXISTS-based query building
# ----------------------------------------

def map_conditions_to_attrs(conditions: List[Dict[str, Any]], fields_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a new list with 'variable' replaced by the mapped ORM attribute."""
    out: List[Dict[str, Any]] = []
    for c in conditions:
        v = c["variable"]
        assert v in fields_map, f"Invalid variable: {v}"
        out.append({**c, "variable": fields_map[v]})
    return out


def entity_of(attr: Any) -> Any:
    """Return the ORM entity/aliased class that owns the attribute."""
    try:
        # Typical InstrumentedAttribute
        return attr.class_
    except Exception:
        try:
            # Fallback for relationship attributes
            return attr.parent.entity  # type: ignore[attr-defined]
        except Exception:
            try:
                # Last resort
                return sa_inspect(attr).class_  # type: ignore[attr-defined]
            except Exception:
                return None


def partition_conditions_by_entity(conditions_mapped: List[Dict[str, Any]]) -> Dict[Any, List[Dict[str, Any]]]:
    grouped: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for c in conditions_mapped:
        grouped[entity_of(c["variable"])].append(c)
    return grouped


def and_expr(conds: List[Dict[str, Any]]) -> Any:
    from sqlalchemy import and_, true

    if not conds:
        return true()
    return and_(*[format_condition(c["variable"], c) for c in conds])


# ----------------------------------------
# EXISTS builders (semi-joins)
# ----------------------------------------
from sqlalchemy import select as sa_select


def exists_forms_for_study(forms_group: Dict[Any, List[Dict[str, Any]]]) -> Any:
    """EXISTS subquery for forms correlated by Study."""
    if not any(forms_group.values()):
        return None

    subq = sa_select(1).select_from(ActiveFormAnnotation).where(
        ActiveFormAnnotation.StudyID == Study.StudyID
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
        subq = (
            subq.join(
                FormAnnotationTagLink,
                ActiveFormAnnotation.FormAnnotationID == FormAnnotationTagLink.FormAnnotationID,
                isouter=True,
            )
            .join(
                FormTag,
                FormAnnotationTagLink.TagID == FormTag.TagID,
                isouter=True,
            )
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

    subq = sa_select(1).select_from(ActiveFormAnnotation).where(
        ActiveFormAnnotation.ImageInstanceID == ImageInstance.ImageInstanceID
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
        subq = (
            subq.join(
                FormAnnotationTagLink,
                ActiveFormAnnotation.FormAnnotationID == FormAnnotationTagLink.FormAnnotationID,
                isouter=True,
            )
            .join(
                FormTag,
                FormAnnotationTagLink.TagID == FormTag.TagID,
                isouter=True,
            )
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

    subq = sa_select(1).select_from(ActiveSegmentation).where(
        ActiveSegmentation.ImageInstanceID == ImageInstance.ImageInstanceID
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
        subq = (
            subq.join(
                SegmentationTagLink,
                ActiveSegmentation.SegmentationID == SegmentationTagLink.SegmentationID,
                isouter=True,
            )
            .join(
                SegTag,
                SegmentationTagLink.TagID == SegTag.TagID,
                isouter=True,
            )
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
        sa_select(1)
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
        sa_select(1)
        .select_from(StudyTagLink)
        .where(StudyTagLink.StudyID == Study.StudyID)
        .join(StudyTag, StudyTagLink.TagID == StudyTag.TagID, isouter=True)
    )
    subq = subq.where(and_expr(tags_group[StudyTag]))
    return subq.exists()


class SignatureField(BaseModel):
    """Signature descriptor for a searchable field."""
    name: str
    # Either a primitive type marker or an enum of allowed values
    values: str | list[str]  # 'string' | 'int' | 'float' | 'date' | string[]
    type: Literal['default', 'attribute'] = 'default'
    model: Optional[str] = None
    feature: Optional[str] = None  # NEW: feature name for segmentation-based attributes

class DefaultCondition(BaseModel):
    type: Literal['default'] = 'default'
    variable: searchable_fields
    operator: operators
    value: Union[date, int, float, str, list[str], None]

class AttributeCondition(BaseModel):
    type: Literal['attribute']
    model: str
    variable: str
    operator: operators
    value: Union[int, float, str, list[str], None]
    feature: Optional[str] = None  # NEW: filter by feature name

SearchCondition = Annotated[Union[DefaultCondition, AttributeCondition], Field(discriminator='type')]

class SearchQuery(BaseModel):
    conditions: List[SearchCondition]
    limit: int = 200
    page: int = 0
    order_by: instance_order_by_fields
    order: Literal["ASC", "DESC"] = "ASC"
    include_count: bool = False


class SearchResponse(BaseModel):
    instances: List[InstanceGET]
    studies: List[StudyGET]
    limit: int
    page: int
    count: Optional[int] = None
    result_ids: List[int]
    has_more: bool

# Study search DTOs
class StudySearchCondition(BaseModel):
    variable: study_searchable_fields
    operator: operators
    value: Union[date, int, float, str, list[str], None]  # add list[str]

class StudySearchQuery(BaseModel):
    conditions: List[StudySearchCondition]
    limit: int = 200
    page: int = 0
    order_by: study_order_by_fields
    order: Literal["ASC", "DESC"] = "ASC"
    include_count: bool = False

class StudySearchResponse(BaseModel):
    studies: List[StudyGET]
    instances: List[InstanceMeta]
    limit: int
    page: int
    count: Optional[int] = None
    result_ids: List[int]
    has_more: bool



def _build_study_select(
    conditions: List[Dict[str, Any]],
    order_by: study_order_by_fields,
    order: Literal["ASC", "DESC"],
):
    """
    Build the base Study select using correlated EXISTS for forms and study tags, and apply ordering.
    """
    mapped = map_conditions_to_attrs(conditions, fields_map=study_search_fields_map)
    by_entity = partition_conditions_by_entity(mapped)

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

    sort_col = study_order_by_fields_map[order_by]
    sort_dir = sort_col.asc() if order == "ASC" else sort_col.desc()
    # Add deterministic tiebreaker
    return q.where(where_clause).order_by(sort_dir, Study.StudyID.asc())


def _build_instance_select(
    conditions: List[Dict[str, Any]],
    order_by: instance_order_by_fields,
    order: Literal["ASC", "DESC"],
    db: Session,
):
    """
    Build the base ImageInstance select using correlated EXISTS and apply ordering.
    """
    
    # Split conditions into default and attribute-based based on discriminator
    static_conds_raw: List[Dict[str, Any]] = []
    attr_conds_raw: List[Tuple[str, str, Optional[str], Dict[str, Any]]] = []  # (model_name, attr_name, feature_name, cond)

    for c in conditions:
        if c.get("type") == "attribute":
            model_name = c.get("model")
            attr_name = c.get("variable")
            feature_name = c.get("feature")  # NEW: extract feature (can be None)
            if not model_name or not isinstance(attr_name, str):
                continue
            attr_conds_raw.append((model_name, attr_name, feature_name, c))
        else:
            # Backward-compat: support legacy "Model[Attr]" variables with no type
            var = c.get("variable")
            if isinstance(var, str):
                pa = parse_attribute_var(var)
                if pa is not None:
                    model_name, attr_name = pa
                    attr_conds_raw.append((model_name, attr_name, None, c))
                    continue
            static_conds_raw.append(c)

    mapped = map_conditions_to_attrs(static_conds_raw, fields_map=instance_search_fields_map)
    by_entity = partition_conditions_by_entity(mapped)

    base_entities = {
        ImageInstance, Series, Study, Patient, Project,
        DeviceInstance, DeviceModel, SourceInfo, Scan,
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
        .join_from(ImageInstance, Series, ImageInstance.SeriesID == Series.SeriesID, isouter=True)
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
    from sqlalchemy import select as sa_select
    
    # First, collect all unique attribute definitions we need to look up
    attr_lookups = {}
    for (model_name, attr_name, feature_name, c) in attr_conds_raw:
        key = (model_name, attr_name, feature_name)
        if key not in attr_lookups:
            attr_lookups[key] = []
        attr_lookups[key].append(c)

    # Look up attribute definitions for all unique model/attribute combinations
    # Note: feature doesn't affect which AttributeDefinition to use, only filtering
    attr_defs = {}
    for (model_name, attr_name, feature_name) in attr_lookups.keys():
        attr_def_stmt = (
            select(AttrDef)
            .join(AttributesModelOutput, AttrDef.AttributeID == AttributesModelOutput.AttributeID)
            .join(AttributesModel, AttributesModelOutput.ModelID == AttributesModel.ModelID)
            .where(AttributesModel.ModelName == model_name)
            .where(AttrDef.AttributeName == attr_name)
        )
        attr_def = db.execute(attr_def_stmt).scalar_one_or_none()
        
        if not attr_def:
            continue
        
        # Store with full key including feature for later lookup
        attr_defs[(model_name, attr_name, feature_name)] = attr_def
    
    # Build EXISTS subqueries using the correct attribute definitions
    for (model_name, attr_name, feature_name, c) in attr_conds_raw:
        attr_def = attr_defs.get((model_name, attr_name, feature_name))
        if not attr_def:
            continue
        
        # Single subquery with outer joins to handle all three entity types
        subq = (
            sa_select(1)
            .select_from(AttrVal)
            .join(AttrDef, AttrVal.AttributeID == AttrDef.AttributeID)
            .join(AttributesModel, AttrVal.ModelID == AttributesModel.ModelID)
            # Outer join to Segmentation (will be NULL if AttributeValue is not for a Segmentation)
            .outerjoin(Segmentation, AttrVal.SegmentationID == Segmentation.SegmentationID)
            # Outer join to ModelSegmentation (will be NULL if AttributeValue is not for a ModelSegmentation)
            .outerjoin(ModelSegmentation, AttrVal.ModelSegmentationID == ModelSegmentation.ModelSegmentationID)
            # ROBUST: Join SegmentationModel early to get its Feature
            .outerjoin(SegmentationModel, ModelSegmentation.ModelID == SegmentationModel.ModelID)
            .where(
                # Match if ANY of the three paths lead to this ImageInstance
                or_(
                    AttrVal.ImageInstanceID == ImageInstance.ImageInstanceID,
                    Segmentation.ImageInstanceID == ImageInstance.ImageInstanceID,
                    ModelSegmentation.ImageInstanceID == ImageInstance.ImageInstanceID
                )
            )
            .where(AttributesModel.ModelName == model_name)
            .where(AttrDef.AttributeName == attr_name)
            .where(format_attr_condition_with_definition(attr_def, c))
        )
        
        # ROBUST: Add feature filter if specified - simpler join logic
        if feature_name:
            subq = subq.outerjoin(
                Feature,
                or_(
                    # Direct Segmentation path
                    Segmentation.FeatureID == Feature.FeatureID,
                    # ModelSegmentation path through SegmentationModel (already joined above)
                    SegmentationModel.FeatureID == Feature.FeatureID
                )
            ).where(Feature.FeatureName == feature_name)
        
        and_predicates.append(subq.exists())

    where_clause = and_(*and_predicates) if and_predicates else true()

    sort_col = instance_order_by_fields_map[order_by]
    sort_dir = sort_col.asc() if order == "ASC" else sort_col.desc()

    final_query = (
        q.filter(ImageInstance.Modality.is_not(None))
         .where(where_clause)
         .order_by(sort_dir, ImageInstance.ImageInstanceID.asc())
    )
    return final_query


@router.post("/instances/search", response_model=SearchResponse, response_model_exclude_none=True)
async def search_instances(
    query: SearchQuery,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    params = query.model_dump()
    conditions = params.get("conditions", {})

    limit = params.get("limit", 200)
    page = params.get("page", 0)
    offset = limit * page

    instances_stmt = _build_instance_select(conditions, params["order_by"], params["order"], db).options(
        selectinload(ImageInstance.Series).selectinload(Series.Study).selectinload(Study.Patient).selectinload(Patient.Project),
        selectinload(ImageInstance.DeviceInstance).selectinload(DeviceInstance.DeviceModel),
        selectinload(ImageInstance.SourceInfo),
        selectinload(ImageInstance.Scan),
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(ImageInstanceTagLink.Tag),
        # attributes
        selectinload(ImageInstance.AttributeValues).selectinload(AttrVal.AttributeDefinition),
        selectinload(ImageInstance.AttributeValues).selectinload(AttrVal.ProducingModel),
    )

    instances = db.execute(instances_stmt.limit(limit + 1).offset(offset)).scalars().all()
    
    has_more = len(instances) > limit
    if has_more:
        instances = instances[:limit]

    if not instances:
        return {"instances": [], "studies": [], "limit": limit, "page": page, "count": None, "result_ids": [], "has_more": False}

    # Build studies in the instance order
    seen: set[int] = set()
    study_ids_ordered: list[int] = []
    for inst in instances:
        st = inst.Series.Study if inst.Series and inst.Series.Study else None
        if st and st.StudyID not in seen:
            seen.add(st.StudyID)
            study_ids_ordered.append(st.StudyID)

    studies_dtos: list[StudyGET] = []
    if study_ids_ordered:
        studies_stmt = select(Study).where(Study.StudyID.in_(study_ids_ordered)).options(
            selectinload(Study.Series).selectinload(Series.ImageInstances.and_(~ImageInstance.Inactive))
        )
        studies = db.execute(studies_stmt).scalars().all()
        s_order = {sid: i for i, sid in enumerate(study_ids_ordered)}
        studies.sort(key=lambda s: s_order[s.StudyID])
        studies_dtos = [DTOConverter.study_to_get(s, include_series=True, with_tag_metadata=True) for s in studies]

    count = None
    if params.get("include_count"):
        count = db.execute(select(func.count()).select_from(instances_stmt.subquery())).scalar_one()

    return {
        "instances": [DTOConverter.image_instance_to_get(i, with_tag_metadata=True) for i in instances],
        "studies": studies_dtos,
        "limit": limit,
        "page": page,
        "count": count,
        "result_ids": [i.ImageInstanceID for i in instances],
        "has_more": has_more,
    }

# New endpoint: /studies/search
@router.post("/studies/search", response_model=StudySearchResponse, response_model_exclude_none=True)
async def search_studies(
    query: StudySearchQuery,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    params = query.model_dump()
    conditions = params.get("conditions", {})

    limit = params.get("limit", 200)
    page = params.get("page", 0)
    offset = limit * page

    studies_stmt = _build_study_select(conditions, params["order_by"], params["order"]).options(
        selectinload(Study.Series).selectinload(Series.ImageInstances.and_(~ImageInstance.Inactive))
    )

    studies = db.execute(studies_stmt.limit(limit + 1).offset(offset)).scalars().all()
    has_more = len(studies) > limit
    if has_more:
        studies = studies[:limit]

    if not studies:
        return {"studies": [], "instances": [], "limit": limit, "page": page, "count": None, "result_ids": [], "has_more": False}

    study_ids = [s.StudyID for s in studies]
    instances_q = (
        select(ImageInstance)
        .where(~ImageInstance.Inactive)
        .join(Series, ImageInstance.SeriesID == Series.SeriesID)
        .where(Series.StudyID.in_(study_ids))
        .options(
            selectinload(ImageInstance.Series).selectinload(Series.Study).selectinload(Study.Patient).selectinload(Patient.Project),
            selectinload(ImageInstance.DeviceInstance).selectinload(DeviceInstance.DeviceModel),
            selectinload(ImageInstance.SourceInfo),
            selectinload(ImageInstance.Scan),
            selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(ImageInstanceTagLink.Tag),
            selectinload(ImageInstance.AttributeValues).selectinload(AttrVal.AttributeDefinition),
            selectinload(ImageInstance.AttributeValues).selectinload(AttrVal.ProducingModel),
        )
        .distinct()
    )
    instances = db.execute(instances_q).scalars().all()

    

    count = None
    if params.get("include_count"):
        count = db.execute(select(func.count()).select_from(studies_stmt.subquery())).scalar_one()

    order = {i: idx for idx, i in enumerate(study_ids)}
    studies.sort(key=lambda s: order[s.StudyID])

    return {
        "studies": [DTOConverter.study_to_get(s, include_series=True, with_tag_metadata=True) for s in studies],
        "instances": [DTOConverter.image_instance_to_get(i, with_tag_metadata=True) for i in instances],
        "limit": limit,
        "page": page,
        "count": count,
        "result_ids": study_ids,
        "has_more": has_more,
    }

@router.get("/instances/search/signature", response_model=list[SignatureField])
async def instances_signature(db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    """Return signature metadata for instance search fields."""
    items: list[SignatureField] = []

    # Enum-backed
    items.append(SignatureField(name="Laterality", values=[e.value for e in ImgLaterality]))
    items.append(SignatureField(name="Modality", values=[e.value for e in ImgModality]))
    items.append(SignatureField(name="ETDRS Field", values=[e.value for e in ImgETDRS]))
    items.append(SignatureField(name="Patient Sex", values=[e.value for e in PatientSex]))

    # DB-derived lists
    projects = db.execute(select(Project.ProjectName).distinct()).scalars().all()
    items.append(SignatureField(name="Project Name", values=sorted(projects)))

    model_ids = db.execute(select(DeviceModel.DeviceModelID).distinct()).scalars().all()
    items.append(SignatureField(name="Device Model ID", values=[str(v) for v in sorted(model_ids)]))

    feat_names = db.execute(select(Feature.FeatureName).distinct()).scalars().all()
    items.append(SignatureField(name="Segmentation Feature Name", values=sorted(feat_names)))

    seg_creators = db.execute(
        select(Creator.CreatorName)
        .join(Segmentation, Segmentation.CreatorID == Creator.CreatorID)
        .where(~Segmentation.Inactive)
        .distinct()
    ).scalars().all()
    items.append(SignatureField(name="Segmentation Creator Name", values=sorted(seg_creators)))

    seg_tag_names = db.execute(
        select(Tag.TagName)
        .join(SegmentationTagLink, SegmentationTagLink.TagID == Tag.TagID)
        .distinct()
    ).scalars().all()
    items.append(SignatureField(name="Segmentation Tag Name", values=sorted(seg_tag_names)))

    form_schema_names = db.execute(select(FormSchema.SchemaName).distinct()).scalars().all()
    items.append(SignatureField(name="Form Schema Name", values=sorted(form_schema_names)))

    form_creators = db.execute(
        select(Creator.CreatorName)
        .join(FormAnnotation, FormAnnotation.CreatorID == Creator.CreatorID)
        .where(~FormAnnotation.Inactive)
        .distinct()
    ).scalars().all()
    items.append(SignatureField(name="Form Creator Name", values=sorted(form_creators)))

    form_tag_names = db.execute(
        select(Tag.TagName)
        .join(FormAnnotationTagLink, FormAnnotationTagLink.TagID == Tag.TagID)
        .distinct()
    ).scalars().all()
    items.append(SignatureField(name="Form Tag Name", values=sorted(form_tag_names)))

    image_tag_names = db.execute(
        select(Tag.TagName)
        .join(ImageInstanceTagLink, ImageInstanceTagLink.TagID == Tag.TagID)
        .distinct()
    ).scalars().all()
    items.append(SignatureField(name="Image Tag Name", values=sorted(image_tag_names)))

    # Attributes signature with feature context
    # Query existing AttributeValues to find which model+feature combinations exist

    # Query 1: AttributeValues linked to Segmentation
    seg_query = (
        select(
            AttrDef.AttributeName,
            AttrDef.AttributeDataType,
            AttributesModel.ModelName,
            Feature.FeatureName
        )
        .select_from(AttrVal)
        .join(AttrDef, AttrVal.AttributeID == AttrDef.AttributeID)
        .join(AttributesModel, AttrVal.ModelID == AttributesModel.ModelID)
        .join(Segmentation, AttrVal.SegmentationID == Segmentation.SegmentationID)
        .join(Feature, Segmentation.FeatureID == Feature.FeatureID)
        .where(AttrDef.AttributeDataType != AttributeDataType.JSON)
    )

    # Query 2: AttributeValues linked to ModelSegmentation
    modelseg_query = (
        select(
            AttrDef.AttributeName,
            AttrDef.AttributeDataType,
            AttributesModel.ModelName,
            Feature.FeatureName
        )
        .select_from(AttrVal)
        .join(AttrDef, AttrVal.AttributeID == AttrDef.AttributeID)
        .join(AttributesModel, AttrVal.ModelID == AttributesModel.ModelID)
        .join(ModelSegmentation, AttrVal.ModelSegmentationID == ModelSegmentation.ModelSegmentationID)
        .join(SegmentationModel, ModelSegmentation.ModelID == SegmentationModel.ModelID)
        .join(Feature, SegmentationModel.FeatureID == Feature.FeatureID)
        .where(AttrDef.AttributeDataType != AttributeDataType.JSON)
    )

    # Query 3: AttributeValues directly linked to ImageInstance (no feature)
    # Use literal(None) for better cross-database compatibility
    direct_query = (
        select(
            AttrDef.AttributeName,
            AttrDef.AttributeDataType,
            AttributesModel.ModelName,
            literal(None).label('FeatureName')  # NULL as FeatureName
        )
        .select_from(AttrVal)
        .join(AttrDef, AttrVal.AttributeID == AttrDef.AttributeID)
        .join(AttributesModel, AttrVal.ModelID == AttributesModel.ModelID)
        .where(AttrVal.ImageInstanceID.is_not(None))
        .where(AttrDef.AttributeDataType != AttributeDataType.JSON)
    )

    # Combine all three with UNION and get distinct results
    combined_query = union_all(seg_query, modelseg_query, direct_query).subquery()
    distinct_query = select(combined_query).distinct()
    attr_rows = db.execute(distinct_query).all()

    # Convert to SignatureFields with deduplication
    seen = set()
    for name, dtype, model_name, feature_name in attr_rows:
        key = (name, model_name, feature_name)
        if key in seen:
            continue
        seen.add(key)
        
        val = "string" if dtype == AttributeDataType.String else ("int" if dtype == AttributeDataType.Int else "float")
        items.append(SignatureField(
            name=name, 
            values=val, 
            type='attribute', 
            model=model_name,
            feature=feature_name  # Will be None for direct image attributes
        ))

    # Free-text/number defaults
    items.append(SignatureField(name="Image DBID", values="int"))
    items.append(SignatureField(name="Color Fundus Quality", values="float"))
    items.append(SignatureField(name="Study Date", values="date"))
    items.append(SignatureField(name="Patient Identifier", values="string"))
    items.append(SignatureField(name="Patient Birthdate", values="date"))

    return items

@router.get("/studies/search/signature", response_model=list[SignatureField])
async def studies_signature(db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    """Return signature metadata for study search fields."""
    items: list[SignatureField] = []

    # Enum-backed
    items.append(SignatureField(name="Patient Sex", values=[e.value for e in PatientSex]))

    # DB-derived
    projects = db.execute(select(Project.ProjectName).distinct()).scalars().all()
    items.append(SignatureField(name="Project Name", values=sorted(projects)))

    form_schema_names = db.execute(select(FormSchema.SchemaName).distinct()).scalars().all()
    items.append(SignatureField(name="Form Schema Name", values=sorted(form_schema_names)))

    form_creators = db.execute(
        select(Creator.CreatorName)
        .join(FormAnnotation, FormAnnotation.CreatorID == Creator.CreatorID)
        .where(~FormAnnotation.Inactive)
        .distinct()
    ).scalars().all()
    items.append(SignatureField(name="Form Creator Name", values=sorted(form_creators)))

    form_tag_names = db.execute(
        select(Tag.TagName)
        .join(FormAnnotationTagLink, FormAnnotationTagLink.TagID == Tag.TagID)
        .distinct()
    ).scalars().all()
    items.append(SignatureField(name="Form Tag Name", values=sorted(form_tag_names)))

    study_tag_names = db.execute(
        select(Tag.TagName)
        .join(StudyTagLink, StudyTagLink.TagID == Tag.TagID)
        .distinct()
    ).scalars().all()
    items.append(SignatureField(name="Study Tag Name", values=sorted(study_tag_names)))

    # Typed free-entry fields
    items.append(SignatureField(name="Study Date", values="date"))
    items.append(SignatureField(name="Study Description", values="string"))
    items.append(SignatureField(name="Study Round", values="int"))
    items.append(SignatureField(name="Study Instance UID", values="string"))
    items.append(SignatureField(name="Patient Identifier", values="string"))
    items.append(SignatureField(name="Patient Birthdate", values="date"))

    return items