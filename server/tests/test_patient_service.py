import pytest

from eyened_orm import Patient, Project
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.patient_repository import PatientRepository

from server.services.exceptions import NotFoundError
from server.services.patient_service import PatientService


def _make_patient(session, identifier: str = "ID1") -> Patient:
    project = Project(ProjectName=f"Project-{identifier}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=identifier, ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    return patient


def test_get_patient_returns_the_patient(session):
    # An existing patient is returned by the service unchanged.
    patient = _make_patient(session)

    service = PatientService(PatientRepository())
    result = service.get_patient(session, patient.PatientID)

    assert result.PatientIdentifier == "ID1"


def test_get_patient_unknown_id_raises_not_found(session):
    # A missing patient makes the service raise NotFoundError (→ 404 via handler).
    service = PatientService(PatientRepository())

    with pytest.raises(NotFoundError):
        service.get_patient(session, 999_999)
