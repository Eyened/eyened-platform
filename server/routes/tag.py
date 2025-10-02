from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from eyened_orm import Tag, CreatorTagLink
from ..db import get_db
from .auth import CurrentUser, get_current_user
from ..dtos.dtos_aux import TagPUT, TagPATCH, TagGET
from ..dtos.dto_converter import DTOConverter

router = APIRouter()

@router.post("/tags", response_model=TagGET)
async def create_tag(dto: TagPUT, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    tag = Tag(
        TagName=dto.name,
        TagDescription=dto.description,
        TagType=dto.tag_type,
        CreatorID=current_user.id,
    )
    db.add(tag); db.commit(); db.refresh(tag)
    return DTOConverter.tag_to_get(tag)

@router.get("/tags", response_model=list[TagGET])
async def list_tags(db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    rows = db.scalars(select(Tag)).all()
    return [DTOConverter.tag_to_get(t) for t in rows]

@router.patch("/tags/{tag_id}", response_model=TagGET)
async def patch_tag(tag_id: int, dto: TagPATCH, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if dto.name is not None:
        tag.TagName = dto.name
    if dto.description is not None:
        tag.TagDescription = dto.description
    if dto.tag_type is not None:
        tag.TagType = dto.tag_type
    db.commit(); db.refresh(tag)
    return DTOConverter.tag_to_get(tag)

@router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(tag_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    db.delete(tag); db.commit()
    return Response(status_code=204)

@router.post("/tags/{tag_id}/star", status_code=204)
async def star_tag(tag_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    # idempotent insert
    if not db.get(CreatorTagLink, {"TagID": tag_id, "CreatorID": current_user.id}):
        db.add(CreatorTagLink(TagID=tag_id, CreatorID=current_user.id))
        db.commit()
    return Response(status_code=204)

@router.delete("/tags/{tag_id}/star", status_code=204)
async def unstar_tag(tag_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    link = db.get(CreatorTagLink, {"TagID": tag_id, "CreatorID": current_user.id})
    if link:
        db.delete(link); db.commit()
    return Response(status_code=204)
