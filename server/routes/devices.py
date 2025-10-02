from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from eyened_orm import DeviceModel
from ..db import get_db
from .auth import CurrentUser, get_current_user
from ..dtos.dtos_main import DeviceModelGET
from ..dtos.dto_converter import DTOConverter

router = APIRouter()

@router.get("/devices", response_model=list[DeviceModelGET])
async def list_devices(db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    """Return all device models."""
    rows = db.scalars(
        select(DeviceModel).order_by(DeviceModel.Manufacturer.asc(), DeviceModel.ManufacturerModelName.asc())
    ).all()
    return [DTOConverter.device_model_to_get(r) for r in rows]
