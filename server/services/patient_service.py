from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import Patient
from eyened_orm.repositories.patient_repository import PatientRepository
from eyened_orm.authz.scope import AccessScope

from ..db import get_db
from .access_scope import get_access_scope
from .exceptions import NotFoundError


class PatientService:
    """Business logic for patients."""

    def __init__(
        self,
        repository: PatientRepository,
        *,
        scope: AccessScope,
    ) -> None:
        self.repository = repository
        self.scope = scope

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


def get_patient_service(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> PatientService:
    """Default PatientService wiring for FastAPI ``Depends()``."""
    return PatientService(PatientRepository(db, scope=scope), scope=scope)
