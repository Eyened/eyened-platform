from collections import defaultdict
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
from pydantic import BaseModel

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session, aliased, defer

from .auth import manager
from ..db import get_db
from .utils import collect_rows
from .query_utils import apply_filters, decode_params, sqlalchemy_operators

router = APIRouter()

AnnotationCreator = aliased(Creator, name="annotation_creator")
FormCreator = aliased(Creator, name="form_creator")

ActiveAnnotation = aliased(
    Annotation,
    select(Annotation).filter(~Annotation.Inactive).subquery(name="active_annot"),
    name="active_annot",
)
ActiveFormAnnotation = aliased(
    FormAnnotation,
    select(FormAnnotation)
    .filter(~FormAnnotation.Inactive)
    .subquery(name="active_form_annot"),
    name="active_form_annot",
)


# Pydantic models for response schemas
class DataResponse(BaseModel):

    instances: List[Dict]
    series: List[Dict]
    studies: List[Dict]
    patients: List[Dict]
    annotations: List[Dict]
    annotationDatas: List[Dict]
    formAnnotations: List[Dict]

    class Config:
        arbitrary_types_allowed = True


class InstanceResponse(BaseModel):
    count: int
    entities: DataResponse


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
    select(ActiveAnnotation, AnnotationData)
    .select_from(AnnotationData)
    .join(ActiveAnnotation)
    .join(Feature)
    .join(AnnotationType)
    .join(AnnotationCreator)
)

# optimization: skipping FormData, viewer will load on demand
form_query = (
    select(ActiveFormAnnotation)
    .options(defer(ActiveFormAnnotation.FormData))
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
annotation_tables = [ActiveAnnotation, Feature, AnnotationType, AnnotationCreator]
form_tables = [ActiveFormAnnotation, FormSchema, FormCreator]


def get_mappings(tables):
    all_mappings = {}

    for table in tables:
        # Use the original table name, not the alias
        original_table_name = table.__table__.name

        for column in table.__table__.columns:
            if column.name == "Password":
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
    for field, (operator, value) in params.items():
        if field not in mappings:
            continue
        column = mappings[field]
        print("where", column, operator, value)
        query = query.where(sqlalchemy_operators[operator](column, value))
    return query


def run_queries(
    session, params, offset, limit, base_query, annotation_query, form_query
):
    params_decoded = decode_params(params)

    query = apply_filters(base_query, base_mappings, params_decoded)

    if any(field in annotation_mappings for field in params_decoded):
        query = (
            query.join(
                ActiveAnnotation,
                ImageInstance.ImageInstanceID == ActiveAnnotation.ImageInstanceID,
            )
            .join(Feature, ActiveAnnotation.FeatureID == Feature.FeatureID)
            .join(
                AnnotationType,
                ActiveAnnotation.AnnotationTypeID == AnnotationType.AnnotationTypeID,
            )
            .join(
                AnnotationCreator,
                ActiveAnnotation.CreatorID == AnnotationCreator.CreatorID,
            )
        )
        print("joining annotations")
        query = apply_filters(query, annotation_mappings, params_decoded)
    if any(field in form_mappings for field in params_decoded):
        query = (
            query.join(
                ActiveFormAnnotation,
                ActiveFormAnnotation.PatientID == Patient.PatientID,
            )
            .join(
                FormSchema, ActiveFormAnnotation.FormSchemaID == FormSchema.FormSchemaID
            )
            .join(FormCreator, ActiveFormAnnotation.CreatorID == FormCreator.CreatorID)
        )
        print("joining forms")
        query = apply_filters(query, form_mappings, params_decoded)

    instance_query = (
        query.distinct(ImageInstance.ImageInstanceID)
        .order_by(Study.StudyDate)
        .limit(limit)
        .offset(offset)
    )
    instances = session.execute(instance_query).all()
    image_ids = {instance.ImageInstanceID for instance, *_ in instances}

    annotation_query = annotation_query.where(
        ActiveAnnotation.ImageInstanceID.in_(image_ids)
    )
    annotations = session.execute(annotation_query).all()

    patient_ids = {patient.PatientID for _, _, _, patient in instances}
    form_query = form_query.where(ActiveFormAnnotation.PatientID.in_(patient_ids))
    form_annotations = session.scalars(form_query).all()

    return instances, annotations, form_annotations


@router.get("/instances", response_model=InstanceResponse)
async def get_instances(
    request: Request,
    session: Session = Depends(get_db),
    user_id: int = Depends(manager),
):

    limit = int(request.query_params.get("limit", 200))
    page = int(request.query_params.get("page", 0))
    offset = limit * page

    multiparams = request.query_params.multi_items()
    print(multiparams)

    i, a, form_annotations = run_queries(
        session, multiparams, offset, limit, base_query, annotation_query, form_query
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

    return {
        "entities": {
            k: collect_rows(v)
            for k, v in {
                "instances": instances,
                "series": series_set,
                "studies": studies,
                "patients": patients,
                "annotations": annotations,
                "annotationDatas": annotation_datas,
                "formAnnotations": form_annotations,
            }.items()
        },
        "count": len(instances),
    }


@router.get("/instances/images/{dataset_identifier:path}")
async def get_file(
    dataset_identifier: str,
):
    # Set X-Accel-Redirect header to tell NGINX to serve the file
    response = Response()
    response.headers["X-Accel-Redirect"] = "/files/" + dataset_identifier
    return response


@router.get("/instances/thumbnails/{thumbnail_identifier:path}")
async def get_thumb(
    thumbnail_identifier: str,
):
    response = Response()
    response.headers["X-Accel-Redirect"] = "/files/" + thumbnail_identifier
    return response
