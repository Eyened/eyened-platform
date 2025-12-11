from eyened_orm import CreatorTagLink, Tag
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_aux import TagGET, TagPATCH, TagPUT
from ..utils.db_logging import get_db_logger
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.post("/tags", response_model=TagGET)
async def create_tag(
    dto: TagPUT,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    tag = Tag(
        TagName=dto.name,
        TagDescription=dto.description,
        TagType=dto.tag_type,
        CreatorID=current_user.id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    
    # Log tag creation
    logger = get_db_logger()
    if logger:
        logger.log_insert(
            user=current_user.username,
            user_id=current_user.id,
            endpoint="POST /api/tags",
            entity="Tag",
            entity_id=tag.TagID,
            fields={
                "name": tag.TagName,
                "description": tag.TagDescription,
                "tag_type": str(tag.TagType),
            },
        )
    
    return DTOConverter.tag_to_get(tag)


@router.get("/tags", response_model=list[TagGET])
async def list_tags(
    db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
):
    rows = db.scalars(select(Tag)).all()
    return [DTOConverter.tag_to_get(t) for t in rows]


@router.patch("/tags/{tag_id}", response_model=TagGET)
async def patch_tag(
    tag_id: int,
    dto: TagPATCH,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    changes = {}
    if dto.name is not None:
        changes["name"] = f"{tag.TagName} -> {dto.name}"
        tag.TagName = dto.name
    if dto.description is not None:
        changes["description"] = f"{tag.TagDescription} -> {dto.description}"
        tag.TagDescription = dto.description
    if dto.tag_type is not None:
        changes["tag_type"] = f"{tag.TagType} -> {dto.tag_type}"
        tag.TagType = dto.tag_type
    db.commit()
    db.refresh(tag)
    
    # Log tag update
    logger = get_db_logger()
    if logger:
        logger.log_update(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"PATCH /api/tags/{tag_id}",
            entity="Tag",
            entity_id=tag.TagID,
            changes=changes if changes else None,
        )
    
    return DTOConverter.tag_to_get(tag)


@router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    
    # Save tag data for logging before deletion
    deleted_data = {
        "name": tag.TagName,
        "description": tag.TagDescription,
        "tag_type": str(tag.TagType),
    }
    
    db.delete(tag)
    db.commit()
    
    # Log tag deletion
    logger = get_db_logger()
    if logger:
        logger.log_delete(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"DELETE /api/tags/{tag_id}",
            entity="Tag",
            entity_id=tag_id,
            deleted_data=deleted_data,
        )
    
    return Response(status_code=204)


@router.post("/tags/{tag_id}/star", status_code=204)
async def star_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    # idempotent insert
    if not db.get(CreatorTagLink, {"TagID": tag_id, "CreatorID": current_user.id}):
        db.add(CreatorTagLink(TagID=tag_id, CreatorID=current_user.id))
        db.commit()
        
        # Log star creation
        logger = get_db_logger()
        if logger:
            logger.log_insert(
                user=current_user.username,
                user_id=current_user.id,
                endpoint=f"POST /api/tags/{tag_id}/star",
                entity="CreatorTagLink",
                fields={
                    "tag_id": tag_id,
                    "creator_id": current_user.id,
                },
            )
    
    return Response(status_code=204)


@router.delete("/tags/{tag_id}/star", status_code=204)
async def unstar_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    link = db.get(CreatorTagLink, {"TagID": tag_id, "CreatorID": current_user.id})
    if link:
        db.delete(link)
        db.commit()
        
        # Log star deletion
        logger = get_db_logger()
        if logger:
            logger.log_delete(
                user=current_user.username,
                user_id=current_user.id,
                endpoint=f"DELETE /api/tags/{tag_id}/star",
                entity="CreatorTagLink",
                fields={"tag_id": tag_id, "creator_id": current_user.id},
            )
    
    return Response(status_code=204)
