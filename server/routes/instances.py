from typing import Dict, List, Optional

from eyened_orm import (
    Annotation,
    AnnotationData,
    AnnotationType,
    Creator,
    DeviceInstance,
    DeviceModel,
    Feature,
    FormAnnotation,
    FormSchema,
    ImageInstance,
    Patient,
    Project,
    Scan,
    Series,
    SourceInfo,
    Study,
)
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, defer

from .auth import CurrentUser, get_current_user
from ..db import get_db
from .utils import collect_rows
from .query_utils import apply_filters, decode_params, sqlalchemy_operators

router = APIRouter()

AnnotationCreator = aliased(Creator, name="annotation_creator")
FormCreator = aliased(Creator, name="form_creator")

# Pydantic models for response schemas
class DataResponse(BaseModel):

    instances: List[ImageInstance]
    series: List[Series]
    studies: List[Study]
    patients: List[Patient]
    annotations: List[Annotation]
    annotation_data: List[AnnotationData] = Field(alias="annotation-data")
    form_annotations: List[FormAnnotation] = Field(alias="form-annotations")

    class Config:
        arbitrary_types_allowed = True


class InstanceResponse(BaseModel):
    entities: DataResponse
    next_cursor: Optional[str] = None


base_query = (
    select(ImageInstance, Series, Study, Patient)
    .select_from(ImageInstance)
    .filter(~ImageInstance.Inactive)
    .join(Series)
    .join(Study)
    .join(Patient)
    .join(Project)
    .outerjoin(SourceInfo)
    .outerjoin(Scan)
    .outerjoin(DeviceInstance)
    .outerjoin(DeviceModel)
)

annotation_query = (
    select(Annotation, AnnotationData)
    .select_from(Annotation)
    .filter(~Annotation.Inactive)
    .join(Feature)
    .join(AnnotationType)
    .join(AnnotationCreator)
    .outerjoin(AnnotationData)
)

# optimization: skipping FormData, viewer will load on demand
form_query = (
    select(FormAnnotation)
    .options(defer(FormAnnotation.FormData))
    .filter(~FormAnnotation.Inactive)
    .join(Patient)
    .join(FormSchema)
    .join(FormCreator)
    .join(Study, Patient.PatientID == Study.PatientID)
)
base_tables = [
    ImageInstance,
    Series,
    Study,
    Patient,
    Project,
    DeviceInstance,
    DeviceModel,
    SourceInfo,
    Scan,
]
annotation_tables = [Annotation, Feature, AnnotationType, AnnotationCreator]
form_tables = [FormAnnotation, FormSchema, FormCreator]


def get_mappings(tables):
    all_mappings = {}

    for table in tables:
        # Use the original table name, not the alias
        original_table_name = table.__table__.name

        for column in table.__table__.columns:
            if column.name == "Password":
                continue
            # Skip foreign keys
            if column.foreign_keys:
                continue
            # Modality is defined on ImageInstance and Feature, but we want to use the value from ImageInstance
            if column.name == "Modality" and original_table_name == "Feature":
                continue

            col = getattr(table, column.key)

            # Use the original table name in the mapping
            all_mappings[f"{original_table_name}.{column.name}"] = col
            if column.name not in all_mappings:
                # First encounter only
                all_mappings[column.name] = col
    return all_mappings


base_mappings = get_mappings(base_tables)
annotation_mappings = get_mappings(annotation_tables)
form_mappings = get_mappings(form_tables)


def apply_filters(query, mappings, params):
    for (field, operator), value in params.items():
        if field not in mappings:
            continue
        column = mappings[field]
        query = query.where(sqlalchemy_operators[operator](column, value))
    return query


def run_queries(
    session, params, cursor, limit, base_query, annotation_query, form_query
):
    params_decoded = decode_params(params)
    if cursor:
        query = query.filter(Study.StudyDate <= cursor)

    query = apply_filters(base_query, base_mappings, params_decoded)

    if any(field in annotation_mappings for field, operator in params_decoded):
        query = (
            query.join(
                Annotation,
                ImageInstance.ImageInstanceID == Annotation.ImageInstanceID,
            )
            .join(Feature, Annotation.FeatureID == Feature.FeatureID)
            .join(
                AnnotationType,
                Annotation.AnnotationTypeID == AnnotationType.AnnotationTypeID,
            )
            .join(
                AnnotationCreator,
                Annotation.CreatorID == AnnotationCreator.CreatorID,
            )
        )
        query = apply_filters(query, annotation_mappings, params_decoded)
    if any(field in form_mappings for field, operator in params_decoded):
        query = (
            query.join(
                FormAnnotation,
                FormAnnotation.PatientID == Patient.PatientID,
            )
            .join(
                FormSchema, FormAnnotation.FormSchemaID == FormSchema.FormSchemaID
            )
            .join(FormCreator, FormAnnotation.CreatorID == FormCreator.CreatorID)
        )
        query = apply_filters(query, form_mappings, params_decoded)

    instance_query = (
        query.distinct(ImageInstance.ImageInstanceID)
        .order_by(Study.StudyDate)
        .limit(limit + 1)
    )
    instances = session.execute(instance_query).all()
    if len(instances) > limit:
        _, _, last_study, _ = instances[-1]
        next_cursor = last_study.StudyDate
        # run again, but with cursor for max date instead of limit
        instance_query = (
            query.filter(Study.StudyDate <= next_cursor)
            .distinct(ImageInstance.ImageInstanceID)
            .order_by(Study.StudyDate)
        )
        instances = session.execute(instance_query).all()

    else:
        next_cursor = None

    image_ids = {instance.ImageInstanceID for instance, *_ in instances}

    annotation_query = annotation_query.where(
        Annotation.ImageInstanceID.in_(image_ids)
    )
    
    annotations = session.execute(annotation_query).all()

    patient_ids = {patient.PatientID for _, _, _, patient in instances}
    form_query = form_query.where(FormAnnotation.PatientID.in_(patient_ids))
    form_annotations = session.scalars(form_query).all()

    return next_cursor, instances, annotations, form_annotations


@router.get("/instances", response_model=InstanceResponse)
async def get_instances(
    request: Request,
    session: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):

    cursor = request.query_params.get("cursor")
    limit = int(request.query_params.get("limit", 200))

    multiparams = request.query_params.multi_items()

    next_cursor, i, a, form_annotations = run_queries(
        session, multiparams, cursor, limit, base_query, annotation_query, form_query
    )

    instances = set()
    series_set = set()
    studies = set()
    patients = set()
    annotations = set()
    annotation_datas = set()

    for instance, series, study, patient in i:        
        instances.add(instance)
        series_set.add(series)
        studies.add(study)
        patients.add(patient)
    for annotation, annotation_data in a:
        annotations.add(annotation)
        annotation_datas.add(annotation_data)

    response = {
        "entities": {
            k: collect_rows(v)
            for k, v in {
                "instances": instances,
                "series": series_set,
                "studies": studies,
                "patients": patients,
                "annotations": annotations,
                "annotation-data": annotation_datas,
                "form-annotations": form_annotations,
            }.items()
        }
    }
    if next_cursor:
        response["next_cursor"] = next_cursor.isoformat()
    return response


@router.get("/instances/images/{dataset_identifier:path}")
async def get_file(
    dataset_identifier: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    # Set X-Accel-Redirect header to tell NGINX to serve the file
    response = Response()
    response.headers["X-Accel-Redirect"] = "/files/" + dataset_identifier
    return response


@router.get("/instances/thumbnails/{thumbnail_identifier:path}")
async def get_thumb(
    thumbnail_identifier: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    response = Response()
    response.headers["X-Accel-Redirect"] = "/thumbnails/" + thumbnail_identifier
    return response
