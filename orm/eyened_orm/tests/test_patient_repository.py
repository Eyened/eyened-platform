from eyened_orm import Patient, Project
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.patient_repository import PatientRepository


def _make_patient(session, identifier: str = "ID1") -> Patient:
    project = Project(ProjectName=f"Project-{identifier}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=identifier, ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    return patient


def test_get_with_attributes_returns_the_patient(session):
    """Looking up an existing patient by id returns that patient."""
    patient = _make_patient(session)

    result = PatientRepository().get_with_attributes(session, patient.PatientID)

    assert result is not None
    assert result.PatientIdentifier == "ID1"


def test_get_with_attributes_unknown_id_returns_none(session):
    """An unknown id returns None — the repository never raises for "not found"."""
    assert PatientRepository().get_with_attributes(session, 999_999) is None
