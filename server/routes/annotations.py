import os
import select
from typing import Dict, List, Optional
from datetime import datetime

from eyened_orm import Annotation, AnnotationData
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user
from ..db import get_db

router = APIRouter()


class AnnotationCreate(BaseModel):
    PatientID: int
    StudyID: int
    SeriesID: int
    ImageInstanceID: int
    AnnotationReferenceID: int | None = None
    CreatorID: int
    FeatureID: int
    AnnotationTypeID: int


class AnnotationResponse(BaseModel):
    AnnotationID: int
    PatientID: int
    StudyID: int
    SeriesID: int
    ImageInstanceID: int
    AnnotationReferenceID: int | None
    CreatorID: int
    FeatureID: int
    AnnotationTypeID: int
    Created: datetime
    Inactive: bool


class AnnotationDataCreate(BaseModel):
    AnnotationID: int
    ScanNr: int
    MediaType: str
    ValueFloat: float | None = None
    ValueInt: int | None = None


class AnnotationDataResponse(BaseModel):
    AnnotationID: int
    ScanNr: int
    MediaType: str
    ValueFloat: float | None
    ValueInt: int | None


@router.post("/annotations", response_model=AnnotationResponse)
async def create_annotation(
    annotation: AnnotationCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    new_annotation = Annotation()
    for key, value in annotation.dict().items():
        setattr(new_annotation, key, value)
    
    new_annotation.Created = datetime.now()
    db.add(new_annotation)
    db.commit()
    db.refresh(new_annotation)
    return new_annotation


@router.get("/annotations", response_model=List[AnnotationResponse])
async def get_annotations(
    patient_id: Optional[int] = None,
    study_id: Optional[int] = None,
    series_id: Optional[int] = None,
    image_instance_id: Optional[int] = None,
    feature_id: Optional[int] = None,
    annotation_type_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    query = select(Annotation).filter(~Annotation.Inactive)
    
    if patient_id is not None:
        query = query.filter(Annotation.PatientID == patient_id)
    if study_id is not None:
        query = query.filter(Annotation.StudyID == study_id)
    if series_id is not None:
        query = query.filter(Annotation.SeriesID == series_id)
    if image_instance_id is not None:
        query = query.filter(Annotation.ImageInstanceID == image_instance_id)
    if feature_id is not None:
        query = query.filter(Annotation.FeatureID == feature_id)
    if annotation_type_id is not None:
        query = query.filter(Annotation.AnnotationTypeID == annotation_type_id)
    
    return db.scalars(query).all()


@router.get("/annotations/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation = db.get(Annotation, annotation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation


@router.delete("/annotations/{annotation_id}", status_code=204)
async def delete_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation = db.get(Annotation, annotation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation not found")

    annotation.Inactive = True
    db.commit()
    return Response(status_code=204)


@router.post("/annotation-data", response_model=AnnotationDataResponse)
async def create_annotation_data(
    data: AnnotationDataCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        annotation = db.get(Annotation, data.AnnotationID)
        if annotation is None:
            raise HTTPException(status_code=404, detail="Annotation not found")

        file_extension = "png" if data.MediaType == "image/png" else "bin"
        annotation_data = AnnotationData.create(annotation, file_extension, data.ScanNr)
        
        if data.ValueFloat is not None:
            annotation_data.ValueFloat = data.ValueFloat
        if data.ValueInt is not None:
            annotation_data.ValueInt = data.ValueInt

        db.add(annotation_data)
        db.commit()
        db.refresh(annotation_data)
        return annotation_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating annotation data: {e}")


@router.get("/annotation-data/{data_id}", response_model=AnnotationDataResponse)
async def get_annotation_data(
    data_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation_data = AnnotationData.from_composite_id(data_id, db)
    if annotation_data is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")
    return annotation_data


@router.get("/annotation-data/{data_id}/file")
async def get_annotation_data_file(
    data_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation_data = AnnotationData.from_composite_id(data_id, db)
    if annotation_data is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")

    filename = annotation_data.path
    if not filename.exists():
        raise HTTPException(status_code=404, detail="Annotation data file not found")

    headers = {}
    if filename.suffix == ".gz":
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Encoding": "gzip",
        }

    return FileResponse(str(filename), headers=headers)


@router.put("/annotation-data/{data_id}/file", status_code=204)
async def update_annotation_data_file(
    data_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation_data = AnnotationData.from_composite_id(data_id, db)
    if annotation_data is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")

    filename = annotation_data.path
    os.makedirs(filename.parent, exist_ok=True)
    
    data = await request.body()
    with open(filename, "wb") as f:
        f.write(data)
    return Response(status_code=204)


@router.delete("/annotation-data/{data_id}", status_code=204)
async def delete_annotation_data(
    data_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation_data = AnnotationData.from_composite_id(data_id, db)
    if annotation_data is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")

    db.delete(annotation_data)
    db.commit()
    return Response(status_code=204)