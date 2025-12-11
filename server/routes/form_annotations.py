from typing import List, Optional

from eyened_orm import (
    FormAnnotation,
    FormAnnotationTagLink,
    ImageInstance,
    ImageInstanceTagLink,
    Study,
    StudyTagLink,
    Tag,
)
from eyened_orm.tag import TagType
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..utils.db_logging import get_db_logger
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_aux import ObjectTagPATCH, ObjectTagPOST, TagMeta
from ..dtos.dtos_main import FormAnnotationGET, FormAnnotationPATCH, FormAnnotationPUT
from .auth import CurrentUser, get_current_user

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
        Laterality=payload.get("laterality"),
        CreatorID=current_user.id,
        SubTaskID=payload.get("sub_task_id"),
        FormData=payload.get("form_data"),
        FormAnnotationReferenceID=payload.get("form_annotation_reference_id"),
    )

    db.add(new_annotation)
    db.commit()
    db.refresh(new_annotation)
    
    # Log form annotation creation
    logger = get_db_logger()
    if logger:
        logger.log_insert(
            user=current_user.username,
            user_id=current_user.id,
            endpoint="POST /api/form-annotations",
            entity="FormAnnotation",
            entity_id=new_annotation.FormAnnotationID,
            fields={
                "form_schema_id": new_annotation.FormSchemaID,
                "patient_id": new_annotation.PatientID,
                "study_id": new_annotation.StudyID,
                "image_instance_id": new_annotation.ImageInstanceID,
                "sub_task_id": new_annotation.SubTaskID,
            },
        )
    
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
    query = (
        select(FormAnnotation)
        .filter(~FormAnnotation.Inactive)
        .options(
            selectinload(FormAnnotation.FormAnnotationTagLinks).selectinload(
                FormAnnotationTagLink.Tag
            ),
            selectinload(FormAnnotation.FormAnnotationTagLinks).selectinload(
                FormAnnotationTagLink.Creator
            ),
            selectinload(FormAnnotation.Study)
            .selectinload(Study.StudyTagLinks)
            .selectinload(StudyTagLink.Tag),
            selectinload(FormAnnotation.Study)
            .selectinload(Study.StudyTagLinks)
            .selectinload(StudyTagLink.Creator),
            selectinload(FormAnnotation.ImageInstance)
            .selectinload(ImageInstance.ImageInstanceTagLinks)
            .selectinload(ImageInstanceTagLink.Tag),
            selectinload(FormAnnotation.ImageInstance)
            .selectinload(ImageInstance.ImageInstanceTagLinks)
            .selectinload(ImageInstanceTagLink.Creator),
        )
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
            selectinload(FormAnnotation.FormAnnotationTagLinks).selectinload(
                FormAnnotationTagLink.Tag
            ),
            selectinload(FormAnnotation.FormAnnotationTagLinks).selectinload(
                FormAnnotationTagLink.Creator
            ),
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

    payload = annotation.dict(exclude_unset=True)

    if "form_schema_id" in payload:
        existing_annotation.FormSchemaID = payload["form_schema_id"]
    if "patient_id" in payload:
        existing_annotation.PatientID = payload["patient_id"]
    if "study_id" in payload:
        existing_annotation.StudyID = payload["study_id"]
    if "image_instance_id" in payload:
        existing_annotation.ImageInstanceID = payload["image_instance_id"]
    if "laterality" in payload:
        existing_annotation.Laterality = payload["laterality"]
    if "sub_task_id" in payload:
        existing_annotation.SubTaskID = payload["sub_task_id"]
    if "form_data" in payload:
        existing_annotation.FormData = payload["form_data"]
    if "form_annotation_reference_id" in payload:
        existing_annotation.FormAnnotationReferenceID = payload[
            "form_annotation_reference_id"
        ]

    db.commit()
    db.refresh(existing_annotation)
    
    # Log form annotation update
    logger = get_db_logger()
    if logger:
        changes = {k: f"{getattr(existing_annotation, k, None)} -> {v}" for k, v in payload.items()}
        logger.log_update(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"PATCH /api/form-annotations/{annotation_id}",
            entity="FormAnnotation",
            entity_id=annotation_id,
            changes=changes if changes else None,
        )
    
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

    # Save annotation data for logging before soft delete
    deleted_data = {
        "form_schema_id": annotation.FormSchemaID,
        "patient_id": annotation.PatientID,
        "study_id": annotation.StudyID,
        "image_instance_id": annotation.ImageInstanceID,
        "sub_task_id": annotation.SubTaskID,
        "laterality": annotation.Laterality,
        "creator_id": annotation.CreatorID,
    }
    
    annotation.Inactive = True
    db.commit()
    
    # Log form annotation deletion (soft delete)
    logger = get_db_logger()
    if logger:
        logger.log_delete(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"DELETE /api/form-annotations/{annotation_id}",
            entity="FormAnnotation",
            entity_id=annotation_id,
            deleted_data=deleted_data,
        )
    
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
    
    # Log form annotation value update
    logger = get_db_logger()
    if logger:
        logger.log_update(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"PUT /api/form-annotations/{form_annotation_id}/value",
            entity="FormAnnotation",
            entity_id=form_annotation_id,
            changes={"form_data": "updated"},
        )
    
    return Response(status_code=204)


@router.post("/form-annotations/{annotation_id}/tags", response_model=TagMeta)
async def tag_form_annotation(
    annotation_id: int,
    body: ObjectTagPOST,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Attach a Tag to a FormAnnotation by tag ID (idempotent)."""
    ann = db.get(FormAnnotation, annotation_id)
    if not ann:
        raise HTTPException(404, "FormAnnotation not found")
    tag = db.get(Tag, body.tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if tag.TagType != TagType.FormAnnotation:
        raise HTTPException(400, "Tag type must be FormAnnotation")

    link = db.get(
        FormAnnotationTagLink, {"TagID": tag.TagID, "FormAnnotationID": annotation_id}
    )
    if not link:
        link = FormAnnotationTagLink(
            TagID=tag.TagID,
            FormAnnotationID=annotation_id,
            CreatorID=current_user.id,
            Comment=body.comment,
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        link.Tag = tag
        
        # Log tag link creation
        logger = get_db_logger()
        if logger:
            logger.log_insert(
                user=current_user.username,
                user_id=current_user.id,
                endpoint=f"POST /api/form-annotations/{annotation_id}/tags",
                entity="FormAnnotationTagLink",
                fields={
                    "tag_id": tag.TagID,
                    "form_annotation_id": annotation_id,
                    "comment": body.comment,
                },
            )
    else:
        if body.comment is not None:
            link.Comment = body.comment
            db.commit()
            db.refresh(link)
            
            # Log tag link update
            logger = get_db_logger()
            if logger:
                logger.log_update(
                    user=current_user.username,
                    user_id=current_user.id,
                    endpoint=f"POST /api/form-annotations/{annotation_id}/tags",
                    entity="FormAnnotationTagLink",
                    fields={"tag_id": tag.TagID, "form_annotation_id": annotation_id},
                    changes={"comment": f"{link.Comment} -> {body.comment}"},
                )

    return DTOConverter.link_to_tag_metadata(link)


@router.delete("/form-annotations/{annotation_id}/tags/{tag_id}", status_code=204)
async def untag_form_annotation(
    annotation_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove a Tag from a FormAnnotation (idempotent)."""
    ann = db.get(FormAnnotation, annotation_id)
    if not ann:
        raise HTTPException(404, "FormAnnotation not found")
    link = db.get(
        FormAnnotationTagLink, {"TagID": tag_id, "FormAnnotationID": annotation_id}
    )
    if link:
        # Save link data for logging before deletion
        deleted_data = {
            "tag_id": tag_id,
            "form_annotation_id": annotation_id,
            "comment": link.Comment,
            "creator_id": link.CreatorID,
        }
        
        db.delete(link)
        db.commit()
        
        # Log tag link deletion
        logger = get_db_logger()
        if logger:
            logger.log_delete(
                user=current_user.username,
                user_id=current_user.id,
                endpoint=f"DELETE /api/form-annotations/{annotation_id}/tags/{tag_id}",
                entity="FormAnnotationTagLink",
                fields={"tag_id": tag_id, "form_annotation_id": annotation_id},
                deleted_data=deleted_data,
            )
    
    return Response(status_code=204)


@router.patch("/form-annotations/{annotation_id}/tags/{tag_id}", response_model=TagMeta)
async def patch_form_annotation_tag(
    annotation_id: int,
    tag_id: int,
    body: ObjectTagPATCH,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Update comment on an existing FormAnnotation tag link."""
    ann = db.get(FormAnnotation, annotation_id)
    if not ann:
        raise HTTPException(404, "FormAnnotation not found")
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if tag.TagType != TagType.FormAnnotation:
        raise HTTPException(400, "Tag type must be FormAnnotation")

    link = db.get(
        FormAnnotationTagLink, {"TagID": tag_id, "FormAnnotationID": annotation_id}
    )
    if not link:
        raise HTTPException(404, "Link not found")

    if body.comment is not None:
        old_comment = link.Comment
        link.Comment = body.comment
        db.commit()
        db.refresh(link)
        
        # Log tag link update
        logger = get_db_logger()
        if logger:
            logger.log_update(
                user=current_user.username,
                user_id=current_user.id,
                endpoint=f"PATCH /api/form-annotations/{annotation_id}/tags/{tag_id}",
                entity="FormAnnotationTagLink",
                fields={"tag_id": tag_id, "form_annotation_id": annotation_id},
                changes={"comment": f"{old_comment} -> {body.comment}"},
            )
    
    link.Tag = tag
    return DTOConverter.link_to_tag_metadata(link)
