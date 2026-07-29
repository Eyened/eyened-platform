from fastapi import APIRouter, Depends

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_instances import PatientDetailGET
from ..services.patient_service import PatientService, get_patient_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/patients/{patient_id}", response_model=PatientDetailGET)
async def get_patient(
    patient_id: int,
    include_attributes: bool = True,
    service: PatientService = Depends(get_patient_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    patient = service.get_patient(patient_id, include_attributes)
    return DTOConverter.patient_to_detail_get(
        patient, include_attributes=include_attributes
    )
