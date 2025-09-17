from eyened_orm import (
    ImageInstance,
    Tag,
    ImageInstanceTagLink,
)
from eyened_orm.Tag import TagType
from fastapi import APIRouter, Depends, HTTPException, Response

from sqlalchemy.orm import Session, selectinload

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_instances import InstanceGET
from ..dtos.dtos_aux import ObjectTagPOST

from .auth import CurrentUser, get_current_user
from ..db import get_db

router = APIRouter()

@router.get("/instances/{instance_id}", response_model=InstanceGET)
async def get_instance(instance_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    item = db.get(
        ImageInstance,
        instance_id,
        options=(
            selectinload(ImageInstance.ImageInstanceTagLinks)
                .selectinload(ImageInstanceTagLink.Tag),
            selectinload(ImageInstance.ImageInstanceTagLinks)
                .selectinload(ImageInstanceTagLink.Creator),
        ),
    )
    if not item:
        raise HTTPException(404, "ImageInstance not found")
    return DTOConverter.image_instance_to_get(item)


@router.get("/instances/images/{dataset_identifier:path}")
async def get_file(
    dataset_identifier: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    # Set X-Accel-Redirect header to tell NGINX to serve the file
    response = Response()
    response.headers["X-Accel-Redirect"] = "/files/" + dataset_identifier
    return response


@router.get("/instances/thumbnails/{thumbnail_identifier:path}")
async def get_thumb(
    thumbnail_identifier: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    response = Response()
    response.headers["X-Accel-Redirect"] = "/thumbnails/" + thumbnail_identifier
    return response


@router.post("/instances/{instance_id}/tags", status_code=204)
async def tag_instance(instance_id: int, body: ObjectTagPOST, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    """Attach a Tag to an ImageInstance by tag ID (idempotent)."""
    instance = db.get(ImageInstance, instance_id)
    if not instance:
        raise HTTPException(404, "ImageInstance not found")
    tag = db.get(Tag, body.tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if tag.TagType != TagType.ImageInstance:
        raise HTTPException(400, "Tag type must be ImageInstance")
    if not db.get(ImageInstanceTagLink, {"TagID": tag.TagID, "ImageInstanceID": instance_id}):
        db.add(ImageInstanceTagLink(TagID=tag.TagID, ImageInstanceID=instance_id, CreatorID=current_user.id))
        db.commit()
    return Response(status_code=204)

@router.delete("/instances/{instance_id}/tags/{tag_id}", status_code=204)
async def untag_instance(instance_id: int, tag_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    """Remove a Tag from an ImageInstance (idempotent)."""
    instance = db.get(ImageInstance, instance_id)
    if not instance:
        raise HTTPException(404, "ImageInstance not found")
    link = db.get(ImageInstanceTagLink, {"TagID": tag_id, "ImageInstanceID": instance_id})
    if link:
        db.delete(link); db.commit()
    return Response(status_code=204)
