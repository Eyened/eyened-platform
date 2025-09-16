from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Literal, Optional, Union

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
from eyened_orm.ImageInstance import Laterality as ImgLaterality, Modality as ImgModality, ETDRSField as ImgETDRS
from eyened_orm.Patient import SexEnum as PatientSex
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sqlalchemy import select, func, and_, or_, true
from sqlalchemy.orm import Session, aliased, selectinload
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

    'SegmentationFeature Name',  # backward-compat
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
    'Study Instance UID',
    'Patient Identifier',
    'Patient Sex',
    'Patient Birthdate',
    'Project Name',

    'Form Schema Name',
    'Form Creator Name',
    'Form Tag Name',
]

study_search_fields_map: Dict[study_searchable_fields, Any] = {
    'Study Date': Study.StudyDate,
    'Study Description': Study.StudyDescription,
    'Study Round': Study.StudyRound,
    'Study Instance UID': Study.StudyInstanceUid,
    'Patient Identifier': Patient.PatientIdentifier,
    'Patient Sex': Patient.Sex,
    'Patient Birthdate': Patient.BirthDate,
    'Project Name': Project.ProjectName,

    'Form Schema Name': FormSchema.SchemaName,
    'Form Creator Name': FormCreator.CreatorName,
    'Form Tag Name': FormTag.TagName,
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


class SignatureField(BaseModel):
    """Signature descriptor for a searchable field."""
    name: str
    # Either a primitive type marker or an enum of allowed values
    values: str | list[str]  # 'string' | 'int' | 'float' | 'date' | string[]

class SearchCondition(BaseModel):
    variable: searchable_fields
    operator: operators
    value: Union[date, int, float, str, list[str], None]  # add list[str]

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


def _build_instance_ids_select(conditions: List[Dict[str, Any]]):
    """
    Build the base ImageInstance ID select with conditional joins for Segmentation and FormAnnotation.
    """
    requested = {c["variable"] for c in conditions}

    where = create_condition(conditions, fields_map=instance_search_fields_map)

    # Determine needed joins
    needs_seg_feature = bool(requested & {'Feature Name', 'Segmentation Feature Name'})
    needs_seg_creator = 'Segmentation Creator Name' in requested
    needs_seg_tag = 'Segmentation Tag Name' in requested
    needs_seg = needs_seg_feature or needs_seg_creator or needs_seg_tag

    needs_form_schema = 'Form Schema Name' in requested
    needs_form_creator = 'Form Creator Name' in requested
    needs_form_tag = 'Form Tag Name' in requested
    needs_form = needs_form_schema or needs_form_creator or needs_form_tag

    needs_inst_tag = bool(requested & {'Image Tag Name', 'Tag Name'})

    q = (
        select(ImageInstance.ImageInstanceID)
        .join_from(ImageInstance, Series, ImageInstance.SeriesID == Series.SeriesID, isouter=True)
        .join_from(Series, Study, isouter=True)
        .join_from(Study, Patient, isouter=True)
        .join_from(Patient, Project, isouter=True)
        .join_from(ImageInstance, DeviceInstance, isouter=True)
        .join_from(DeviceInstance, DeviceModel, isouter=True)
        .join_from(ImageInstance, SourceInfo, isouter=True)
        .join_from(ImageInstance, Scan, isouter=True)
    )

    if needs_seg:
        q = q.join_from(
            ImageInstance, ActiveSegmentation,
            ActiveSegmentation.ImageInstanceID == ImageInstance.ImageInstanceID, isouter=True
        )
        if needs_seg_feature:
            q = q.join_from(ActiveSegmentation, Feature, isouter=True)
        if needs_seg_creator:
            q = q.join_from(
                ActiveSegmentation, SegCreator,
                ActiveSegmentation.CreatorID == SegCreator.CreatorID, isouter=True
            )
        if needs_seg_tag:
            q = q.join_from(ActiveSegmentation, SegmentationTagLink, isouter=True)\
                 .join_from(SegmentationTagLink, SegTag, isouter=True)

    if needs_form:
        q = q.join_from(
            ImageInstance, ActiveFormAnnotation,
            ActiveFormAnnotation.ImageInstanceID == ImageInstance.ImageInstanceID, isouter=True
        )
        if needs_form_schema:
            q = q.join_from(ActiveFormAnnotation, FormSchema, ActiveFormAnnotation.SchemaID == FormSchema.FormSchemaID, isouter=True)
        if needs_form_creator:
            q = q.join_from(
                ActiveFormAnnotation, FormCreator,
                ActiveFormAnnotation.CreatorID == FormCreator.CreatorID, isouter=True
            )
        if needs_form_tag:
            q = q.join_from(ActiveFormAnnotation, FormAnnotationTagLink, isouter=True)\
                 .join_from(FormAnnotationTagLink, FormTag, isouter=True)

    if needs_inst_tag:
        q = q.join_from(ImageInstance, ImageInstanceTagLink, isouter=True)\
             .join_from(ImageInstanceTagLink, InstTag, isouter=True)

    return (
        q.filter(ImageInstance.Modality.is_not(None))
         .where(where)
         .distinct()
         .order_by(ImageInstance.ImageInstanceID.asc())
    )


def _build_study_ids_select(conditions: List[Dict[str, Any]]):
    """
    Build the base Study ID select with conditional joins for ActiveFormAnnotation.
    """
    requested = {c["variable"] for c in conditions}

    where = create_condition(conditions, fields_map=study_search_fields_map)

    needs_form_schema = 'Form Schema Name' in requested
    needs_form_creator = 'Form Creator Name' in requested
    needs_form_tag = 'Form Tag Name' in requested
    needs_form = needs_form_schema or needs_form_creator or needs_form_tag

    q = (
        select(Study.StudyID)
        .join_from(Study, Patient, onclause=Study.PatientID == Patient.PatientID)
        .join_from(Patient, Project)
        .join_from(Study, StudyTagLink, isouter=True)
        .join_from(StudyTagLink, Tag, isouter=True)
    )

    if needs_form:
        q = q.join_from(Study, ActiveFormAnnotation, ActiveFormAnnotation.StudyID == Study.StudyID, isouter=True)
        if needs_form_schema:
            q = q.join_from(ActiveFormAnnotation, FormSchema, ActiveFormAnnotation.SchemaID == FormSchema.FormSchemaID, isouter=True)
        if needs_form_creator:
            q = q.join_from(
                ActiveFormAnnotation, FormCreator,
                ActiveFormAnnotation.CreatorID == FormCreator.CreatorID, isouter=True
            )
        if needs_form_tag:
            q = q.join_from(ActiveFormAnnotation, FormAnnotationTagLink, isouter=True)\
                 .join_from(FormAnnotationTagLink, FormTag, isouter=True)

    return q.where(where).distinct().order_by(Study.StudyID.asc())


@router.post("/instances/search", response_model=SearchResponse, response_model_exclude_none=True)
async def create_form_annotation(
    query: SearchQuery,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    params = query.model_dump()
    conditions = params.get("conditions", {})

    limit = params.get("limit", 200)
    page = params.get("page", 0)
    offset = limit * page

    base_ids = _build_instance_ids_select(conditions)

    ids = db.execute(base_ids.limit(limit + 1).offset(offset)).scalars().all()
    has_more = len(ids) > limit
    if has_more:
        ids = ids[:limit]

    if not ids:
        return {"instances": [], "studies": [], "limit": limit, "page": page, "count": None, "result_ids": [], "has_more": False}

    instances_stmt = (
        select(ImageInstance)
        .where(ImageInstance.ImageInstanceID.in_(ids))
        .options(
            selectinload(ImageInstance.Series).selectinload(Series.Study).selectinload(Study.Patient).selectinload(Patient.Project),
            selectinload(ImageInstance.DeviceInstance).selectinload(DeviceInstance.DeviceModel),
            selectinload(ImageInstance.SourceInfo),
            selectinload(ImageInstance.Scan),
            selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(ImageInstanceTagLink.Tag),
        )
    )
    instances = db.execute(instances_stmt).scalars().all()
    order = {i: idx for idx, i in enumerate(ids)}
    instances.sort(key=lambda x: order[x.ImageInstanceID])

    # build studies list for these instances
    seen: set[int] = set()
    study_ids_ordered: list[int] = []
    for inst in instances:
        st = inst.Series.Study if inst.Series and inst.Series.Study else None
        if st and st.StudyID not in seen:
            seen.add(st.StudyID)
            study_ids_ordered.append(st.StudyID)

    studies_dtos: list[StudyGET] = []
    if study_ids_ordered:
        studies_stmt = (
            select(Study)
            .where(Study.StudyID.in_(study_ids_ordered))
            .options(selectinload(Study.Series).selectinload(Series.ImageInstances))
        )
        studies = db.execute(studies_stmt).scalars().all()
        # preserve instance-first study order
        s_order = {sid: i for i, sid in enumerate(study_ids_ordered)}
        studies.sort(key=lambda s: s_order[s.StudyID])

        # include series + full instance_ids as-is (no filtering)
        studies_dtos = [DTOConverter.study_to_get(s, include_series=True) for s in studies]

    count = None
    if params.get("include_count"):
        count = db.execute(select(func.count()).select_from(base_ids.subquery())).scalar_one()

    return {
        "instances": [DTOConverter.image_instance_to_get(i) for i in instances],
        "studies": studies_dtos,
        "limit": limit,
        "page": page,
        "count": count,
        "result_ids": ids,           # remains instance IDs
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

    base_ids = _build_study_ids_select(conditions)

    study_ids = db.execute(base_ids.limit(limit + 1).offset(offset)).scalars().all()
    has_more = len(study_ids) > limit
    if has_more:
        study_ids = study_ids[:limit]

    if not study_ids:
        return {"studies": [], "instances": [], "limit": limit, "page": page, "count": None, "result_ids": [], "has_more": False}

    studies_stmt = (
        select(Study)
        .where(Study.StudyID.in_(study_ids))
        .options(
            selectinload(Study.Series).selectinload(Series.ImageInstances)
        )
    )
    studies = db.execute(studies_stmt).scalars().all()

    instances_q = (
        select(ImageInstance)
        .join(Series, ImageInstance.SeriesID == Series.SeriesID)
        .where(Series.StudyID.in_(study_ids))
        .options(
            selectinload(ImageInstance.Series).selectinload(Series.Study).selectinload(Study.Patient).selectinload(Patient.Project),
            selectinload(ImageInstance.DeviceInstance).selectinload(DeviceInstance.DeviceModel),
            selectinload(ImageInstance.SourceInfo),
            selectinload(ImageInstance.Scan),
            selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(ImageInstanceTagLink.Tag),
        )
        .distinct()
    )
    instances = db.execute(instances_q).scalars().all()

    count = None
    if params.get("include_count"):
        count = db.execute(select(func.count()).select_from(base_ids.subquery())).scalar_one()

    order = {i: idx for idx, i in enumerate(study_ids)}
    studies.sort(key=lambda s: order[s.StudyID])

    return {
        "studies": [DTOConverter.study_to_get(s, include_series=True) for s in studies],
        "instances": [DTOConverter.image_instance_to_get(i) for i in instances],
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

    # Typed free-entry fields
    items.append(SignatureField(name="Study Date", values="date"))
    items.append(SignatureField(name="Study Description", values="string"))
    items.append(SignatureField(name="Study Round", values="int"))
    items.append(SignatureField(name="Study Instance UID", values="string"))
    items.append(SignatureField(name="Patient Identifier", values="string"))
    items.append(SignatureField(name="Patient Birthdate", values="date"))

    return items