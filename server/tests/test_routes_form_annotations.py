from datetime import datetime

import pytest
from eyened_orm import AuditLog, Creator, FormAnnotation, FormSchema, Patient, Project
from eyened_orm.project import ExternalEnum

# Deliberately far in the past: any value the UPDATE's onupdate produces is
# newer, so the assertion cannot pass by coincidence.
SEEDED_DATE_MODIFIED = datetime(2020, 1, 1)


@pytest.fixture()
def audit_disabled(client, monkeypatch):
    """Serve requests with the audit sink switched off (EYENED_DBLOG_ENABLED=false).

    AuditService.record() flushes the session to assign the AuditLog PK, and
    that flush also writes out every other pending mutation -- so with auditing
    on, a service that never calls repository.save() still persists, and any
    test of a write-back would pass whether or not the write-back exists.
    Turning the sink off removes that masking flush.

    Patched at the name the service factory reads, not via
    app.dependency_overrides: get_form_annotation_service calls
    get_audit_service(db) as a plain function rather than declaring it as a
    Depends(), so FastAPI never resolves it and an override on it is silently
    inert. Every other service factory wires audit the same way. Settings are
    frozen (DbLogSettings, config.py), so the env flag itself cannot be flipped
    in-process either. This substitutes exactly what get_audit_service returns
    when EYENED_DBLOG_ENABLED=false, leaving the real factory to wire the
    repositories.
    """
    from server.services import form_annotation_service
    from server.services.audit_service import AuditService

    monkeypatch.setattr(
        form_annotation_service,
        "get_audit_service",
        lambda db: AuditService(db, enabled=False),
    )


def _make_annotation(session) -> FormAnnotation:
    """Seed a FormAnnotation carrying an obviously stale DateModified."""
    project = Project(ProjectName="P-fa", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier="ID-fa", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    schema = FormSchema(SchemaName="S-fa")
    session.add(schema)
    session.flush()
    creator = Creator(CreatorName="c-fa", IsHuman=True)
    session.add(creator)
    session.flush()
    annotation = FormAnnotation(
        FormSchemaID=schema.FormSchemaID,
        PatientID=patient.PatientID,
        CreatorID=creator.CreatorID,
        FormData={"answer": 1},
        DateModified=SEEDED_DATE_MODIFIED,
    )
    session.add(annotation)
    session.commit()
    return annotation


def test_patch_form_annotation_refreshes_date_modified_without_the_audit_flush(
    client, session, audit_disabled
):
    """PATCH /form-annotations/{id} returns a DateModified produced by the
    UPDATE, with the audit sink disabled.

    This is the only test in the suite that can fail if a service's
    repository.save() write-back is removed. FormAnnotation.DateModified is a
    SQL-side onupdate=func.now(), so it changes only when the UPDATE statement
    actually runs; without save()'s flush the response is serialized (FastAPI
    builds it inside the dependency exit stack, before get_db commits) from the
    unflushed in-memory object and still carries the seeded value.

    Discriminator: replacing FormAnnotationRepository.save's body with `pass`
    makes this fail with the seeded 2020-01-01 timestamp. Asserting against the
    same session that made the change is not enough on its own -- the identity
    map returns the same object either way, which is why this asserts on the
    HTTP response body.
    """
    annotation = _make_annotation(session)

    response = client.patch(
        f"/form-annotations/{annotation.FormAnnotationID}",
        json={"form_data": {"answer": 2}},
    )

    assert response.status_code == 200, response.text
    date_modified = response.json()["date_modified"]
    assert date_modified is not None
    assert datetime.fromisoformat(date_modified) > SEEDED_DATE_MODIFIED

    # Control on the fixture itself: if the override failed to take and the real
    # sink ran, its flush would satisfy the assertion above for the wrong
    # reason, leaving the discriminator dead without anything saying so.
    assert session.query(AuditLog).count() == 0
