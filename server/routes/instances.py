from eyened_orm import (
    ImageInstance,
)
from fastapi import APIRouter, Depends, HTTPException, Response

from sqlalchemy.orm import Session

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_instances import InstanceGET

from .auth import CurrentUser, get_current_user
from ..db import get_db

router = APIRouter()

@router.get("/instances/{instance_id}", response_model=InstanceGET)
async def get_instance(instance_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    item = db.get(ImageInstance, instance_id)
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
