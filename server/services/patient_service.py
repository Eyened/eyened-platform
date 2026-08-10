from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import Patient
from eyened_orm.repositories.patient_repository import PatientRepository

from ..db import get_db
from .exceptions import NotFoundError


class PatientService:
    """Business logic for patients."""

    def __init__(self, repository: PatientRepository) -> None:
        self.repository = repository

    def get_patient(
        self,
        patient_id: int,
        include_attributes: bool = True,
    ) -> Patient:
        """Return the patient with the given id.

        Raises:
            NotFoundError: If no patient with ``patient_id`` exists.
        """
        patient = self.repository.get_with_attributes(
            patient_id, include_attributes
        )
        if patient is None:
            raise NotFoundError(f"Patient {patient_id} not found")
        return patient


def get_patient_service(db: Session = Depends(get_db)) -> PatientService:
    """Default PatientService wiring for FastAPI ``Depends()``."""
    return PatientService(PatientRepository(db))
