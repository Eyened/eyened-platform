from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from eyened_orm import ImageInstance
from ..db import get_db
from .auth import CurrentUser, get_current_user
from ..dtos.dtos_instances import InstanceGET
from ..dtos.dto_converter import DTOConverter

router = APIRouter()

@router.get("/instances/{instance_id}", response_model=InstanceGET)
async def get_instance(instance_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    item = db.get(ImageInstance, instance_id)
    if not item:
        raise HTTPException(404, "ImageInstance not found")
    return DTOConverter.image_instance_to_get(item)
