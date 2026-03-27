from eyened_orm import AttributeValue, Patient
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_instances import PatientDetailGET
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/patients/{patient_id}", response_model=PatientDetailGET)
async def get_patient(
    patient_id: int,
    include_attributes: bool = True,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    opts = [selectinload(Patient.Project)]
    if include_attributes:
        opts.append(
            selectinload(Patient.AttributeValues).selectinload(
                AttributeValue.AttributeDefinition
            )
        )

    patient = db.get(Patient, patient_id, options=tuple(opts))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    return DTOConverter.patient_to_detail_get(
        patient, include_attributes=include_attributes
    )
