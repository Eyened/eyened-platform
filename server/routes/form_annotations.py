from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import FormAnnotation

from ..db import get_db
from .auth import CurrentUser, get_current_user

router = APIRouter()


class FormAnnotationCreate(BaseModel):
    PatientID: int
    StudyID: int | None = None
    ImageInstanceID: int | None = None
    FormSchemaID: int
    CreatorID: int
    SubTaskID: int | None = None
    FormAnnotationReferenceID: int | None = None


class FormAnnotationResponse(BaseModel):
    FormAnnotationID: int
    FormSchemaID: int
    PatientID: int
    StudyID: int | None
    ImageInstanceID: int | None
    CreatorID: int
    SubTaskID: int | None
    FormData: dict | None
    DateInserted: datetime
    DateModified: datetime | None
    FormAnnotationReferenceID: int | None
    Inactive: bool

    class Config:
        arbitrary_types_allowed = True


@router.post("/form-annotations", response_model=FormAnnotationResponse)
async def create_form_annotation(
    annotation: FormAnnotationCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    new_annotation = FormAnnotation()
    for key, value in annotation.dict().items():
        if value is not None:
            setattr(new_annotation, key, value)

    new_annotation.DateInserted = datetime.now()
    db.add(new_annotation)
    db.commit()
    db.refresh(new_annotation)
    return new_annotation


@router.get("/form-annotations", response_model=List[FormAnnotationResponse])
async def get_form_annotations(
    patient_id: Optional[int] = None,
    study_id: Optional[int] = None,
    image_instance_id: Optional[int] = None,
    form_schema_id: Optional[int] = None,
    sub_task_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    query = select(FormAnnotation).filter(~FormAnnotation.Inactive)

    if patient_id is not None:
        query = query.filter(FormAnnotation.PatientID == patient_id)
    if study_id is not None:
        query = query.filter(FormAnnotation.StudyID == study_id)
    if image_instance_id is not None:
        query = query.filter(FormAnnotation.ImageInstanceID == image_instance_id)
    if form_schema_id is not None:
        query = query.filter(FormAnnotation.FormSchemaID == form_schema_id)
    if sub_task_id is not None:
        query = query.filter(FormAnnotation.SubTaskID == sub_task_id)

    return db.scalars(query).all()


@router.get("/form-annotations/{annotation_id}", response_model=FormAnnotationResponse)
async def get_form_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation = db.get(FormAnnotation, annotation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="FormAnnotation not found")
    return annotation


@router.put("/form-annotations/{annotation_id}", response_model=FormAnnotationResponse)
async def update_form_annotation(
    annotation_id: int,
    annotation: FormAnnotationCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    existing_annotation = db.get(FormAnnotation, annotation_id)
    if existing_annotation is None:
        raise HTTPException(status_code=404, detail="FormAnnotation not found")

    for key, value in annotation.dict().items():
        setattr(existing_annotation, key, value)

    db.commit()
    db.refresh(existing_annotation)
    return existing_annotation


@router.delete("/form-annotations/{annotation_id}", status_code=204)
async def delete_form_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation = db.get(FormAnnotation, annotation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="FormAnnotation not found")

    annotation.Inactive = True
    db.commit()
    return Response(status_code=204)


@router.put("/form-annotations/{form_annotation_id}/value", status_code=204)
async def update_form_annotation_value(
    form_annotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation = db.get(FormAnnotation, form_annotation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="FormAnnotation not found")

    form_data = await request.json()
    annotation.FormData = form_data
    db.commit()
    return Response(status_code=204)


@router.get("/form-annotations/{form_annotation_id}/value")
async def get_form_annotation_value(
    form_annotation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation = db.get(FormAnnotation, form_annotation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="FormAnnotation not found")

    return annotation.FormData
