from typing import Dict, List, Optional

from eyened_orm import (
    # Annotation,
    # AnnotationData,
    # AnnotationType,
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
    Segmentation,
)
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, defer

from .auth import CurrentUser, get_current_user
from ..db import get_db
from .utils import collect_rows
from .query_utils import apply_filters, decode_params, sqlalchemy_operators

router = APIRouter()


# Pydantic models for response schemas
class DataResponse(BaseModel):

    instances: List[ImageInstance]
    series: List[Series]
    studies: List[Study]
    patients: List[Patient]
    # annotations: List[Annotation]
    # annotation_data: List[AnnotationData] = Field(alias="annotation-data")
    segmentations: List[Segmentation]
    form_annotations: List[FormAnnotation] = Field(alias="form-annotations")

    class Config:
        arbitrary_types_allowed = True


class InstanceResponse(BaseModel):
    entities: DataResponse
    next_cursor: Optional[str] = None


def join_tables(query):
    return (
        query.join(Project, Project.ProjectID == Patient.ProjectID)
        .outerjoin(SourceInfo)
        .outerjoin(Scan)
        .outerjoin(DeviceInstance)
        .outerjoin(DeviceModel)
    )


base_query = join_tables(
    select(ImageInstance, Series, Study, Patient)
    .select_from(ImageInstance)
    .filter(~ImageInstance.Inactive)
    .join(Series, Series.SeriesID == ImageInstance.SeriesID)
    .join(Study, Study.StudyID == Series.StudyID)
    .join(Patient, Patient.PatientID == Study.PatientID)
)

segmentation_sub_query = join_tables(
    select(Segmentation.ImageInstanceID)
    .select_from(Segmentation)
    .filter(~Segmentation.Inactive)
    .join(Feature)
    # .join(AnnotationType)
    .join(Creator)
    .join(ImageInstance, ImageInstance.ImageInstanceID == Segmentation.ImageInstanceID)
    .join(Series, Series.SeriesID == ImageInstance.SeriesID)
    .join(Study, Study.StudyID == Series.StudyID)
    .join(Patient, Patient.PatientID == Study.PatientID)
)

form_sub_query = join_tables(
    select(FormAnnotation.PatientID)
    .select_from(FormAnnotation)
    .filter(~FormAnnotation.Inactive)
    .join(FormSchema)
    .join(Creator)
    .join(Patient, Patient.PatientID == FormAnnotation.PatientID)
    .outerjoin(Study, Study.PatientID == Patient.PatientID)
    .outerjoin(Series, Series.StudyID == Study.StudyID)
    .outerjoin(ImageInstance, ImageInstance.SeriesID == Series.SeriesID)
)

segmentation_query = (
    select(Segmentation)
    .select_from(Segmentation)
    .filter(~Segmentation.Inactive)
    .join(Feature)
    # .join(AnnotationType)
    .join(Creator)
)


# optimization: skipping FormData, viewer will load on demand
form_query = (
    select(FormAnnotation)
    .options(defer(FormAnnotation.FormData))
    .filter(~FormAnnotation.Inactive)
    .join(Patient)
    .join(FormSchema)
    .join(Creator)
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
segmentation_tables = [Segmentation, Feature, Creator]
form_tables = [FormAnnotation, FormSchema, Creator]


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
segmentation_mappings = get_mappings(segmentation_tables)
form_mappings = get_mappings(form_tables)


def apply_filters(query, mappings, params):
    for (field, operator), value in params.items():
        if field not in mappings:
            continue
        column = mappings[field]
        query = query.where(sqlalchemy_operators[operator](column, value))
    return query


def run_queries(
    session, params, cursor, limit, base_query, segmentation_query, form_query
):
    params_decoded = decode_params(params)
    
    query = apply_filters(base_query, base_mappings, params_decoded)
    if cursor:
        query = query.filter(Study.StudyDate <= cursor)

    query = query.distinct(ImageInstance.ImageInstanceID).order_by(Study.StudyDate)

    filter_instance_ids = set()
    filter_patient_ids = set()
    if any(field in segmentation_mappings for field, operator in params_decoded):
        sub_query = apply_filters(
            segmentation_sub_query,
            {**segmentation_mappings, **base_mappings},
            params_decoded,
        )
        filter_instance_ids = set(session.execute(sub_query).scalars().all())

    if any(field in form_mappings for field, operator in params_decoded):
        sub_query = apply_filters(
            form_sub_query, {**form_mappings, **base_mappings}, params_decoded
        )
        filter_patient_ids = set(session.execute(sub_query).scalars().all())

    if filter_instance_ids or filter_patient_ids:
        query = query.filter(
            or_(
                ImageInstance.ImageInstanceID.in_(filter_instance_ids),
                Patient.PatientID.in_(filter_patient_ids),
            )
        )

    query = query.order_by(Study.StudyDate).limit(limit + 1)

    instances = session.execute(query).all()
    if len(instances) > limit:
        _, _, last_study, _ = instances[-1]
        next_cursor = last_study.StudyDate
        # run again, but with cursor for max date instead of limit
        query = (
            query.filter(Study.StudyDate <= next_cursor)
            .distinct(ImageInstance.ImageInstanceID)
            .order_by(Study.StudyDate)
        )
        instances = session.execute(query).all()

    else:
        next_cursor = None

    image_ids = {instance.ImageInstanceID for instance, *_ in instances}

    segmentation_query = segmentation_query.where(Segmentation.ImageInstanceID.in_(image_ids))

    segmentations = session.scalars(segmentation_query).all()

    patient_ids = {patient.PatientID for _, _, _, patient in instances}
    form_query = form_query.where(FormAnnotation.PatientID.in_(patient_ids))
    form_annotations = session.scalars(form_query).all()

    return next_cursor, instances, segmentations, form_annotations


@router.get("/instances", response_model=InstanceResponse)
async def get_instances(
    request: Request,
    session: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):

    cursor = request.query_params.get("cursor")
    limit = int(request.query_params.get("limit", 200))

    multiparams = request.query_params.multi_items()

    next_cursor, i, segmentations, form_annotations = run_queries(
        session, multiparams, cursor, limit, base_query, segmentation_query, form_query
    )
    instances = {instance for instance, _, _, _ in i}
    series = {series for _, series, _, _ in i}
    studies = {study for _, _, study, _ in i}
    patients = {patient for _, _, _, patient in i}

    print(instances)
    print(segmentations)

    response = {
        "entities": {
            k: collect_rows(v)
            for k, v in {
                "instances": instances,
                "series": series,   
                "studies": studies,
                "patients": patients,
                "segmentations": segmentations,
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
