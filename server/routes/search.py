from collections import defaultdict
from typing import Any, Dict, List, Literal

from eyened_orm import (
    Creator,
    DeviceModel,
    Feature,
    FormAnnotation,
    ImageInstance,
    ImageInstanceTag,
    Patient,
    Project,
    Scan,
    Series,
    SourceInfo,
    Study,
    Segmentation,
    Tag
)
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sqlalchemy import select, text
from sqlalchemy.orm import Session, aliased
from sqlalchemy.dialects import mysql

from .auth import CurrentUser, get_current_user
from ..db import get_db
from ..dtos import InstanceGET, DTOConverter

router = APIRouter()


# list of properties that are searchable with identifier and mapped ORM property
searchable_fields = Literal['Image DBID', 'Laterality', 'Modality', 'Anatomic Region', 'ETDRS Field', 'Color Fundus Quality', 'Study Date', 'Patient Identifier', 'Patient Sex', 'Patient Birthdata', 'Project Name', 'Device Model ID', 'Feature Name', 'Tag Name']

operators = Literal[">", "<", ">=", "<=", "==", "!="]

instance_search_fields_map: Dict[searchable_fields, Any] = {
    'Image DBID': ImageInstance.ImageInstanceID,
    'Laterality': ImageInstance.Laterality,
    'Modality': ImageInstance.Modality,
    'Anatomic Region': ImageInstance.AnatomicRegion,
    'ETDRS Field': ImageInstance.ETDRSField,
    'Color Fundus Quality': ImageInstance.CFQuality,
    'Study Date': Study.StudyDate,
    'Patient Identifier': Patient.PatientIdentifier,
    'Patient Sex': Patient.Sex,
    'Patient Birthdata': Patient.BirthDate,
    'Project Name': Project.ProjectName,
    'Device Model ID': DeviceModel.DeviceModelID,
    'Feature Name': Feature.FeatureName,
    'Tag Name': Tag.TagName,
}




def get_series_studies_patients(session, instances: List[ImageInstance]):
    series_ids = [instance.SeriesID for instance in instances]
    # get series, studies, and patients for provided instances
    rows = (
        session.query(Series, Study, Patient)
        .join(Study, Series.StudyID == Study.StudyID)
        .join(Patient, Study.PatientID == Patient.PatientID)
        .filter(Series.SeriesID.in_(series_ids))
        .all()
    )
    return {
        "series": set([row[0] for row in rows]),
        "studies": set([row[1] for row in rows]),
        "patients": set([row[2] for row in rows]),
    }

def format_condition(variable, condition):
    operator = condition["operator"]
    value = condition["value"]
    if value is None:
        return "{} {} NULL".format(variable, operator)
    if isinstance(value, list):
        return "{} IN ({})".format(variable, ", ".join(map(str, value)))
    return '{} {} "{}"'.format(variable, operator, value)

def create_condition(conditions):
    for condition in conditions:
        assert (
            condition["variable"] in instance_search_fields_map
        ), f"Invalid variable: {condition['variable']}"
        condition["variable"] = instance_search_fields_map[condition["variable"]]

    # Group conditions by variable
    conditions_by_variable = defaultdict(list)
    for condition in conditions:
        conditions_by_variable[condition["variable"]].append(condition)

    # Generate the WHERE clause
    where_clauses = []
    for variable, conditions in conditions_by_variable.items():
        # Check if the value is a date
        is_date = variable in (
            instance_search_fields_map['Study Date'],
            instance_search_fields_map['Patient Birthdata'],
        )
        join_operator = " AND " if is_date else " OR "

        where_clauses.append(
            "({})".format(
                join_operator.join([format_condition(variable, c) for c in conditions])
            )
        )
    return text(" AND ".join(where_clauses))


class SearchCondition(BaseModel):
    variable: searchable_fields
    operator: operators
    value: Any

class SearchQuery(BaseModel):
    conditions: List[Dict[str, Any]]
    limit: int = 200
    page: int = 0


class SearchResponse(BaseModel):
    instances: List[InstanceGET]
    limit: int
    page: int
    count: int
    result_ids: List[int]
    query: str

@router.post("/instances/search", response_model=SearchResponse)
async def create_form_annotation(
    query: SearchQuery,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    params = query.get_json()
    conditions = params.get("conditions", {})

    limit = params.get("limit", 200)
    page = params.get("page", 0)

    offset = limit * page

    # alias the annotation tables to filter out inactive annotations
    ActiveSegmentation = aliased(
        Segmentation,
        select(Segmentation).filter(~Segmentation.Inactive).subquery(name="active_annot"),
        name="active_annot",
    )
    ActiveFormAnnotation = aliased(
        FormAnnotation,
        select(FormAnnotation)
        .filter(~FormAnnotation.Inactive)
        .subquery(name="active_form_annot"),
        name="active_form_annot",
    )

    # TODO: join with other tables?
    # perhaps FormSchema? Task?
    where = create_condition(conditions)
    query = (
        select(ImageInstance)
        .join_from(
            ImageInstance,
            Series,
            ImageInstance.SeriesID == Series.SeriesID,
            isouter=True,
        )
        .join_from(Series, Study, isouter=True)
        .join_from(Study, Patient, isouter=True)
        .join_from(Patient, Project, isouter=True)
        .join_from(ImageInstance, Device, isouter=True)
        .join_from(ImageInstance, SourceInfo, isouter=True)
        .join_from(ImageInstance, Scan, isouter=True)
        .join_from(ImageInstance, ImageInstanceTag, isouter=True)
        .join_from(ImageInstanceTag, Tag, isouter=True)
        .join_from(
            ImageInstance,
            ActiveFormAnnotation,
            ActiveFormAnnotation.ImageInstanceID == ImageInstance.ImageInstanceID,
            isouter=True,
        )
        .join_from(
            ImageInstance,
            ActiveSegmentation,
            ActiveSegmentation.ImageInstanceID == ImageInstance.ImageInstanceID,
            isouter=True,
        )
        .join_from(ActiveSegmentation, Feature, isouter=True)
        .join_from(
            ActiveSegmentation,
            Creator,
            ActiveSegmentation.CreatorID == Creator.CreatorID,
            isouter=True,
        )
        .filter(ImageInstance.Modality.is_not(None))
        .where(where)
        .distinct()
    )

    instances = db.execute(query.limit(limit).offset(offset)).scalars().all()

    # COUNT using subquery
    subquery = query.compile(dialect=mysql.dialect())
    # print(str(subquery))
    count_query = f"SELECT COUNT(*) FROM({subquery}) as MYSUBQ"
    count = db.execute(text(str(count_query))).first()[0]


    return {
        "instances": [DTOConverter.instance_to_get(instance) for instance in instances],
        "limit": limit,
        "page": page,
        "count": count,
        "result_ids": [instance.ImageInstanceID for instance in instances],
        "query": str(subquery),
    }