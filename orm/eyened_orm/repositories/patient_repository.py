from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from eyened_orm import AttributeValue, Patient
from eyened_orm.authz.scope import AccessScope


class PatientRepository:
    """Data access for Patient rows."""

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

    def get_with_attributes(
        self,
        patient_id: int,
        include_attributes: bool = True,
    ) -> Patient | None:
        """Return a patient by id with Project (and optionally attributes) eager-loaded."""
        opts = [selectinload(Patient.Project)]
        if include_attributes:
            # Mirror server/routes/patients.py: load the attribute definition AND
            # its producing-model provenance so patient_to_detail_get stays N+1-free.
            opts.append(
                selectinload(Patient.AttributeValues).selectinload(
                    AttributeValue.AttributeDefinition
                )
            )
            opts.append(
                selectinload(Patient.AttributeValues).selectinload(
                    AttributeValue.ProducingModel
                )
            )
        return self._session.get(Patient, patient_id, options=tuple(opts))
