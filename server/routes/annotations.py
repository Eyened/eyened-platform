import os
from typing import Dict, Optional

from eyened_orm import Annotation, AnnotationData
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth import manager
from .config import settings
from .db import get_db

router = APIRouter()

@router.post("/annotations/new", response_model=Dict)
async def create_annotation(
        properties: dict,
        db: Session = Depends(get_db),
        user_id: int = Depends(manager)
):
    annotation = Annotation()
    keys = [
        'PatientID', 'StudyID', 'SeriesID', 'ImageInstanceID', 'AnnotationReferenceID',
        'CreatorID', 'FeatureID', 'AnnotationTypeID'
    ]
    for key, value in properties.items():
        if key in keys:
            setattr(annotation, key, value)

    db.add(annotation)
    db.commit()
    return annotation.to_dict()


@router.post("/annotationDatas/new", response_model=Dict)
async def create_annotationdata(
        properties: dict,
        db: Session = Depends(get_db),
        user_id: int = Depends(manager)
):
    try:
        annotation = Annotation.by_id(db, properties['AnnotationID'])
        scan_nr = properties['ScanNr']

        # TODO: implement better way of finding file type
        media_type = properties['MediaType']
        if media_type == 'image/png':
            file_extension = 'png'
        elif media_type == 'application/octet-stream':
            file_extension = 'bin'
        annotationData = AnnotationData.create(
            annotation, file_extension, scan_nr)
        db.add(annotationData)
        db.commit()
        return annotationData.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error creating annotation data: {e}")


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(
    annotation_id: int, db: Session = Depends(get_db),
    user_id: int = Depends(manager)
):
    annot = db.query(Annotation).get(annotation_id)
    if annot is None:
        raise HTTPException(status_code=404, detail="Annotation not found")

    annot.Inactive = True
    db.add(annot)
    db.commit()
    return Response(status_code=204)


def get_annotation_data(annotation_data_id: str, db: Session):
    annotation_id, scan_nr = map(int, annotation_data_id.split("_"))
    return (
        db.query(AnnotationData)
        .filter_by(AnnotationID=annotation_id, ScanNr=scan_nr)
        .first()
    )


@router.delete("/annotationDatas/{annotation_data_id}")
async def delete_annotation_data(
        annotation_data_id: str,
        db: Session = Depends(get_db),
        user_id: int = Depends(manager)
):
    annotation_data = get_annotation_data(annotation_data_id, db)
    if annotation_data is None:
        raise HTTPException(
            status_code=404, detail="Annotation data not found")

    db.delete(annotation_data)
    db.commit()
    return Response(status_code=204)


@router.get("/annotationDatas/{annotation_data_id}/value")
async def get_annotation_data_value(
    annotation_data_id: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(manager),
):
    annotation_data = get_annotation_data(annotation_data_id, db)
    if annotation_data is None:
        raise HTTPException(
            status_code=404, detail="Annotation data not found")

    file_path = os.path.join(
        settings.annotations_path, annotation_data.DatasetIdentifier
    )

    headers = {}
    # Manually set headers for zipped files
    if file_path.endswith('.gz'):
        headers = {
            'Content-Type': 'application/octet-stream',
            'Content-Encoding': 'gzip'
        }
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404, detail="Annotation data file not found")

    return FileResponse(file_path, headers=headers)


@router.put("/annotationDatas/{annotation_data_id}/value")
async def update_annotation_data_value(
    annotation_data_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(manager),
):
    annotation_data = get_annotation_data(annotation_data_id, db)
    if annotation_data is None:
        raise HTTPException(
            status_code=404, detail="Annotation data not found")

    # store to disk
    filename = os.path.join(
        settings.annotations_path, annotation_data.DatasetIdentifier
    )
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    data = await request.body()
    with open(filename, "wb") as f:
        f.write(data)
    return Response(status_code=204)


class AnnotationDataParameters(BaseModel):
    valuefloat: Optional[float] = None
    valueint: Optional[int] = None


@router.get("/annotationDatas/{annotation_data_id}/parameters", response_model=AnnotationDataParameters)
async def get_annotation_data_parameters(
    annotation_data_id: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(manager),
):
    annotation_data = get_annotation_data(annotation_data_id, db)

    if annotation_data is None:
        raise HTTPException(
            status_code=404, detail="Annotation data not found")

    return {
        'valuefloat': annotation_data.ValueFloat,
        'valueint': annotation_data.ValueInt
    }


@router.put("/annotationDatas/{annotation_data_id}/parameters")
async def update_annotation_data_parameters(
    annotation_data_id: str,
    request: AnnotationDataParameters,
    db: Session = Depends(get_db),
    user_id: int = Depends(manager),
):
    annotation_data = get_annotation_data(annotation_data_id, db)

    if annotation_data is None:
        raise HTTPException(
            status_code=404, detail="Annotation data not found")

    property_mapping = {
        'valuefloat': 'ValueFloat',
        'valueint': 'ValueInt'
    }

    for key, value in request.model_dump().items():
        property = property_mapping[key]
        setattr(annotation_data, property, value)

    db.add(annotation_data)
    db.commit()
    return Response(status_code=204)
