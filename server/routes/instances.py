from collections import defaultdict
from typing import Dict, List, Optional

from eyened_orm import (Annotation, AnnotationData, AnnotationType, Creator,
                        DeviceInstance, DeviceModel, Feature, FormAnnotation,
                        FormSchema, ImageInstance, Patient, Project, Scan,
                        Series, SourceInfo, Study)
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from routes.query_utils import (apply_filters, decode_params,
                                sqlalchemy_operators)
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session, aliased

from .auth import manager
from .db import get_db
from .utils import collect_rows

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


# Create aliases for Creator table
AnnotationCreator = aliased(Creator)
FormAnnotationCreator = aliased(Creator)

# alias the annotation tables to filter out inactive annotations
ActiveAnnotation = aliased(
    Annotation,
    select(Annotation).filter(
        ~Annotation.Inactive).subquery(name="active_annot"),
    name="active_annot",
)
ActiveFormAnnotation = aliased(
    FormAnnotation,
    select(FormAnnotation)
    .filter(~FormAnnotation.Inactive)
    .subquery(name="active_form_annot"),
    name="active_form_annot",
)
base_query = (
    select(ImageInstance,
           Series,
           Study,
           Patient,
           AnnotationData,
           ActiveAnnotation,
           ActiveFormAnnotation)
    .select_from(ImageInstance)
    .filter(ImageInstance.Inactive == False)    
    .join(Series, ImageInstance.SeriesID == Series.SeriesID)
    .join(Study, Series.StudyID == Study.StudyID)
    .join(Patient, Study.PatientID == Patient.PatientID)
    .join(Project, Patient.ProjectID == Project.ProjectID)
    .join(DeviceInstance, ImageInstance.DeviceInstanceID == DeviceInstance.DeviceInstanceID, isouter=True)
    .join(DeviceModel, DeviceInstance.DeviceModelID == DeviceModel.DeviceModelID, isouter=True)
    .join(SourceInfo, ImageInstance.SourceInfoID == SourceInfo.SourceInfoID, isouter=True)
    .join(Scan, ImageInstance.ScanID == Scan.ScanID, isouter=True)

    # join on ImageInstanceID
    .join(ActiveAnnotation, ActiveAnnotation.ImageInstanceID == ImageInstance.ImageInstanceID, isouter=True)
    .join(AnnotationData, AnnotationData.AnnotationID == ActiveAnnotation.AnnotationID, isouter=True)
    .join(Feature, ActiveAnnotation.FeatureID == Feature.FeatureID, isouter=True)
    .join(AnnotationType, ActiveAnnotation.AnnotationTypeID == AnnotationType.AnnotationTypeID, isouter=True)
    .join(AnnotationCreator, ActiveAnnotation.CreatorID == AnnotationCreator.CreatorID, isouter=True)

    # join on PatientID
    .join(ActiveFormAnnotation, ActiveFormAnnotation.PatientID == Patient.PatientID, isouter=True)
    .join(FormSchema, ActiveFormAnnotation.FormSchemaID == FormSchema.FormSchemaID, isouter=True)
    .join(FormAnnotationCreator, ActiveFormAnnotation.CreatorID == FormAnnotationCreator.CreatorID, isouter=True)
)

all_tables = [
    ImageInstance,
    Series,
    Study,
    Patient,
    Project,
    DeviceInstance,
    DeviceModel,
    SourceInfo,
    Scan,

    AnnotationData,
    ActiveAnnotation,
    Feature,
    AnnotationType,
    AnnotationCreator,

    ActiveFormAnnotation,
    FormSchema,
    FormAnnotationCreator
]

all_mappings = defaultdict(set)

for table in all_tables:
    for column in table.__table__.columns:
        if column.name == 'Password':
            continue
        if column.name == 'Modality' and table.__name__ == 'Feature':
            continue
        if column.name == 'ImageInstanceID' and table.__name__ != 'ImageInstance':
            continue
        if column.name == 'SeriesID' and table.__name__ != 'Series':
            continue
        if column.name == 'StudyID' and table.__name__ != 'Study':
            continue
        if column.name == 'PatientID' and table.__name__ != 'Patient':
            continue
        col = getattr(table, column.key)

        all_mappings[column.name].add(col)


def apply_filters(query, params):

    for field, (operator, value) in params.items():
        if field not in all_mappings:
            continue

        columns = all_mappings[field]
        op_func = sqlalchemy_operators[operator]
        filter = or_(
            op_func(column, value)
            for column in columns
        )
        query = query.where(filter)

    return query


def collect_entities(main):
    instances = set()
    series_set = set()
    studies = set()
    patients = set()
    annotations_set = set()
    annotation_datas = set()
    form_annotations = set()

    for instance, series, study, patient, annotation_data, annotation, form_annotation in main:
        instances.add(instance)
        series_set.add(series)
        studies.add(study)
        patients.add(patient)
        annotations_set.add(annotation)
        annotation_datas.add(annotation_data)
        form_annotations.add(form_annotation)

    return instances, series_set, studies, patients, annotations_set, annotation_datas, form_annotations


def run_base_query(session, params, offset, limit):
    params_decoded = decode_params(params)
    filtered_query = apply_filters(base_query, params_decoded)

    # Create a count query using the filtered query
    count_query = filtered_query.with_only_columns(
        func.count(distinct(ImageInstance.ImageInstanceID))
    )
    images_count = session.execute(count_query).scalar()

    subquery = select(
        filtered_query
        .with_only_columns(distinct(ImageInstance.ImageInstanceID))
        # Order to ensure deterministic pagination
        .order_by(ImageInstance.ImageInstanceID)
        .limit(limit)
        .offset(offset)
        .subquery()
    )

    query = base_query.where(ImageInstance.ImageInstanceID.in_(
        subquery
    ))

    return images_count, session.execute(query).all()


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
    # r = session.execute(select(ImageInstance).where(ImageInstance.ImageInstanceID == 193024)).all()
    # print('??', r)
    
    images_count, main = run_base_query(session, multiparams, offset, limit)

    (instances,
     series,
     studies,
     patients,
     annotations,
     annotation_datas,
     form_annotations) = collect_entities(main)

    return {
        "entities": {
            k: collect_rows(v) for k, v in {
                "instances": instances,
                "series": series,
                "studies": studies,
                "patients": patients,
                "annotations": annotations,
                "annotationDatas": annotation_datas,
                "formAnnotations": form_annotations
            }.items()
        },
        "count": images_count,
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
