from collections import defaultdict
from typing import Dict, List, Optional

from eyened_orm import (Annotation, AnnotationData, AnnotationType, Creator,
                        DeviceInstance, DeviceModel, Feature, FormAnnotation,
                        FormSchema, ImageInstance, Patient, Project, Scan,
                        Series, SourceInfo, Study)
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session, aliased

from .auth import manager
from ..db import get_db
from .utils import collect_rows
from .query_utils import (apply_filters, decode_params,
                                sqlalchemy_operators)

router = APIRouter()


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
    select(Annotation, AnnotationData)
    .select_from(AnnotationData)
    .join(Annotation)
    .filter(~Annotation.Inactive)
    .join(Feature)
    .join(AnnotationType)
    .join(Creator)
)
form_query = (
    select(FormAnnotation)
    .filter(~FormAnnotation.Inactive)
    .join(Patient)    
    .join(FormSchema)
    .join(Creator)
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
    Scan
]
annotation_tables = [
    Annotation,
    Feature,
    AnnotationType,
    Creator,
    AnnotationData
]
form_tables = [
    FormAnnotation,
    FormSchema,
    Creator
]

def get_mappings(tables):
    all_mappings = {}

    for table in tables:
        # Use the original table name, not the alias
        original_table_name = table.__table__.name

        for column in table.__table__.columns:
            if column.name == 'Password':
                continue
            col = getattr(table, column.key)

            # Use the original table name in the mapping
            all_mappings[f'{original_table_name}.{column.name}'] = col
            if column.name not in all_mappings:
                # First encounter only
                all_mappings[column.name] = col
    return all_mappings

base_mappings = get_mappings(base_tables)
annotation_mappings = get_mappings(annotation_tables)
form_mappings = get_mappings(form_tables)

def apply_filters(query, mappings, params):
    applied = False
    for field, (operator, value) in params.items():
        if field not in mappings:
            continue
        applied = True
        column = mappings[field]
        query = query.where(sqlalchemy_operators[operator](column, value))
    return query, applied

def run_queries(session, params, offset, limit, base_query, annotation_query, form_query):
    params_decoded = decode_params(params)

    # Apply filters to each query and track whether filters were applied
    base_query, base_applied = apply_filters(base_query, base_mappings, params_decoded)
    annotation_query, annot_applied = apply_filters(annotation_query, annotation_mappings, params_decoded)
    form_query, form_applied = apply_filters(form_query, form_mappings, params_decoded)

    instances = []
    annotations = []
    form_annotations = []
    
    if base_applied: 
        # CASE 1: Base filters are applied → get images directly
        instances = session.execute(
            base_query.order_by(ImageInstance.ImageInstanceID).limit(limit).offset(offset)
        ).all()
        
        if instances:
            
            # filter form annotations by image instance IDs
            image_ids = {instance.ImageInstanceID for instance, *_ in instances}
            annotation_query = annotation_query.where(Annotation.ImageInstanceID.in_(image_ids))
            annotations = session.execute(annotation_query).all()
            
            if annot_applied:
                # filter only instances that have annotations 
                # the same logic is not applied to form annotations because those are filtered by patient IDs
                # Not sure if this makes sense. 
                # TODO: find a cleaner way to query / filter instances and annotations?
                annotated_instances = {annotation.ImageInstanceID for annotation, _ in annotations}                        
                instances = [row for row in instances if row[0].ImageInstanceID in annotated_instances]
                        
            # filter form annotations by patient IDs    
            patient_ids = {instance.Patient.PatientID for instance, *_ in instances}
            form_query = form_query.where(FormAnnotation.PatientID.in_(patient_ids))
            form_annotations = session.scalars(form_query).all()
            
           
    
    else:
        # CASE 2: No base filters applied
        instance_ids = set()

        if annot_applied: 
            # only retrieve annotations if filters are applied 
            annotations = session.execute(annotation_query).all()
            instance_ids.update(annotation.ImageInstanceID for annotation, _ in annotations)

        if form_applied:
            # only retrieve form annotations if filters are applied
            form_annotations = session.scalars(form_query).all()
            instance_ids.update(form.ImageInstanceID for form in form_annotations)

        instance_ids.delete(None)

        if instance_ids:
            # filter base query by image instance IDs obtained from annotations and/or form annotations
            base_query = base_query.where(ImageInstance.ImageInstanceID.in_(instance_ids))
            instances = session.execute(
                base_query.order_by(ImageInstance.ImageInstanceID).limit(limit).offset(offset)
            ).all()
        else:
            # No filters applied or no matching instances
            pass


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
    
    i, a, form_annotations = run_queries(session, multiparams, offset, limit, base_query, annotation_query, form_query)
    
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
            k: collect_rows(v) for k, v in {
                "instances": instances,
                "series": series_set,
                "studies": studies,
                "patients": patients,
                "annotations": annotations,
                "annotationDatas": annotation_datas,
                "formAnnotations": form_annotations
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
    response.headers["X-Accel-Redirect"] = "/thumbnails/" + thumbnail_identifier
    return response
