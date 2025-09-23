from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from eyened_orm import FormAnnotation, Tag, FormAnnotationTagLink, Study, StudyTagLink, ImageInstance, ImageInstanceTagLink
from eyened_orm.Tag import TagType

from ..db import get_db
from .auth import CurrentUser, get_current_user
from ..dtos.dtos_main import FormAnnotationPUT, FormAnnotationPATCH, FormAnnotationGET
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_aux import ObjectTagPOST, TagMeta

router = APIRouter()


@router.post("/form-annotations", response_model=FormAnnotationGET)
async def create_form_annotation(
    annotation: FormAnnotationPUT,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    # Map DTO snake_case to ORM PascalCase fields
    payload = annotation.dict()
    new_annotation = FormAnnotation(
        FormSchemaID=payload.get("form_schema_id"),
        PatientID=payload.get("patient_id"),
        StudyID=payload.get("study_id"),
        ImageInstanceID=payload.get("image_instance_id"),
        CreatorID=payload.get("creator_id"),
        SubTaskID=payload.get("sub_task_id"),
        FormData=payload.get("form_data"),
        FormAnnotationReferenceID=payload.get("form_annotation_reference_id"),
    )

    db.add(new_annotation)
    db.commit()
    db.refresh(new_annotation)
    return DTOConverter.form_annotation_to_get(new_annotation)


@router.get("/form-annotations", response_model=List[FormAnnotationGET])
async def get_form_annotations(
    patient_id: Optional[int] = None,
    study_id: Optional[int] = None,
    image_instance_id: Optional[int] = None,
    form_schema_id: Optional[int] = None,
    sub_task_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    query = select(FormAnnotation).filter(~FormAnnotation.Inactive).options(
        selectinload(FormAnnotation.FormAnnotationTagLinks).selectinload(FormAnnotationTagLink.Tag),
        selectinload(FormAnnotation.FormAnnotationTagLinks).selectinload(FormAnnotationTagLink.Creator),
        selectinload(FormAnnotation.Study)
            .selectinload(Study.StudyTagLinks).selectinload(StudyTagLink.Tag),
        selectinload(FormAnnotation.Study)
            .selectinload(Study.StudyTagLinks).selectinload(StudyTagLink.Creator),
        selectinload(FormAnnotation.ImageInstance)
            .selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(ImageInstanceTagLink.Tag),
        selectinload(FormAnnotation.ImageInstance)
            .selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(ImageInstanceTagLink.Creator),
    )

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

    orm_rows = db.scalars(query).all()
    return [DTOConverter.form_annotation_to_get(row) for row in orm_rows]


@router.get("/form-annotations/{annotation_id}", response_model=FormAnnotationGET)
async def get_form_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation = db.get(
        FormAnnotation,
        annotation_id,
        options=(
            selectinload(FormAnnotation.FormAnnotationTagLinks).selectinload(FormAnnotationTagLink.Tag),
            selectinload(FormAnnotation.FormAnnotationTagLinks).selectinload(FormAnnotationTagLink.Creator),
        ),
    )
    if annotation is None:
        raise HTTPException(status_code=404, detail="FormAnnotation not found")
    return DTOConverter.form_annotation_to_get(annotation)


@router.patch("/form-annotations/{annotation_id}", response_model=FormAnnotationGET)
async def update_form_annotation(
    annotation_id: int,
    annotation: FormAnnotationPATCH,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    existing_annotation = db.get(FormAnnotation, annotation_id)
    if existing_annotation is None:
        raise HTTPException(status_code=404, detail="FormAnnotation not found")

    if annotation.form_schema_id is not None:
        existing_annotation.FormSchemaID = annotation.form_schema_id
    if annotation.patient_id is not None:
        existing_annotation.PatientID = annotation.patient_id
    if annotation.study_id is not None:
        existing_annotation.StudyID = annotation.study_id
    if annotation.image_instance_id is not None:
        existing_annotation.ImageInstanceID = annotation.image_instance_id
    if annotation.creator_id is not None:
        existing_annotation.CreatorID = annotation.creator_id
    if annotation.sub_task_id is not None:
        existing_annotation.SubTaskID = annotation.sub_task_id
    if annotation.form_data is not None:
        existing_annotation.FormData = annotation.form_data
    if annotation.form_annotation_reference_id is not None:
        existing_annotation.FormAnnotationReferenceID = annotation.form_annotation_reference_id

    db.commit()
    db.refresh(existing_annotation)
    return DTOConverter.form_annotation_to_get(existing_annotation)


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


@router.post("/form-annotations/{annotation_id}/tags", response_model=TagMeta)
async def tag_form_annotation(annotation_id: int, body: ObjectTagPOST, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)) -> TagMeta:
    """Attach a Tag to a FormAnnotation by tag ID (idempotent)."""
    ann = db.get(FormAnnotation, annotation_id)
    if not ann:
        raise HTTPException(404, "FormAnnotation not found")
    tag = db.get(Tag, body.tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if tag.TagType != TagType.FormAnnotation:
        raise HTTPException(400, "Tag type must be FormAnnotation")

    link = db.get(FormAnnotationTagLink, {"TagID": tag.TagID, "FormAnnotationID": annotation_id})
    if not link:
        link = FormAnnotationTagLink(TagID=tag.TagID, FormAnnotationID=annotation_id, CreatorID=current_user.id)
        db.add(link); db.commit(); db.refresh(link)
        link.Tag = tag

    return DTOConverter.link_to_tag_metadata(link)

@router.delete("/form-annotations/{annotation_id}/tags/{tag_id}", status_code=204)
async def untag_form_annotation(annotation_id: int, tag_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    """Remove a Tag from a FormAnnotation (idempotent)."""
    ann = db.get(FormAnnotation, annotation_id)
    if not ann:
        raise HTTPException(404, "FormAnnotation not found")
    link = db.get(FormAnnotationTagLink, {"TagID": tag_id, "FormAnnotationID": annotation_id})
    if link:
        db.delete(link); db.commit()
    return Response(status_code=204)


