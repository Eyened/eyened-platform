from fastapi import APIRouter, Depends

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_main import DeviceModelGET
from ..services.device_service import DeviceService, get_device_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/devices", response_model=list[DeviceModelGET])
async def list_devices(
    service: DeviceService = Depends(get_device_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return all device models."""
    rows = service.list_devices()
    return [DTOConverter.device_model_to_get(r) for r in rows]
