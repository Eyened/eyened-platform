from datetime import datetime
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from eyened_orm import FormAnnotation

from ..db import get_db
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.post("/formAnnotations/new", response_model=Dict)
async def create_form_annotation(
    form_data: dict,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    annotation = FormAnnotation()
    keys = [
        'FormSchemaID', 'PatientID', 'StudyID', 'ImageInstanceID',
        'CreatorID', 'SubTaskID', 'FormData', 'Inactive',
        'FormAnnotationReferenceID'
    ]
    for key, value in form_data.items():
        if key in keys:
            setattr(annotation, key, value)

    annotation.Created = datetime.now()
    db.add(annotation)
    db.commit()

    return annotation.to_dict()



@router.delete("/formAnnotations/{form_annotation_id}", status_code=204)
async def delete_form_annotation(
    form_annotation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    annotation = db.get(FormAnnotation, form_annotation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="FormAnnotation not found")

    annotation.Inactive = True
    db.commit()
    return Response(status_code=204)


@router.put("/formAnnotations/{form_annotation_id}/value", status_code=204)
async def update_form_annotation_value(
    form_annotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    annotation = db.get(FormAnnotation, form_annotation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="FormAnnotation not found")

    form_data = await request.json()
    annotation.FormData = form_data
    db.commit()
    return Response(status_code=204)


@router.get("/formAnnotations/{form_annotation_id}/value")
async def get_form_annotation_value(
    form_annotation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    annotation = db.get(FormAnnotation, form_annotation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="FormAnnotation not found")

    return annotation.FormData


@router.get("/form-annotations")
async def get_form_annotations(
    current_user: CurrentUser = Depends(get_current_user)
):
    # Your existing code here, but use current_user.id instead of user_id
    pass

@router.put("/form-annotations/{annotation_id}")
async def update_form_annotation(
    annotation_id: int,
    current_user: CurrentUser = Depends(get_current_user)
):
    # Your existing code here, but use current_user.id instead of user_id
    pass