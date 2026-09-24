from eyened_orm import Creator, FormAnnotation, FormSchema, Patient, Project
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.form_annotation_repository import (
    FormAnnotationRepository,
)
from eyened_orm.utils.factories import admin_scope


def _make_annotation(
    session,
    key: str,
    *,
    inactive: bool = False,
    study_id: int | None = None,
    image_instance_id: int | None = None,
) -> FormAnnotation:
    """Build the minimal FK graph a FormAnnotation requires; return the row."""
    project = Project(ProjectName=f"P-{key}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"ID-{key}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    schema = FormSchema(SchemaName=f"S-{key}")
    session.add(schema)
    session.flush()
    creator = Creator(CreatorName=f"c-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    ann = FormAnnotation(
        FormSchemaID=schema.FormSchemaID,
        PatientID=patient.PatientID,
        CreatorID=creator.CreatorID,
        StudyID=study_id,
        ImageInstanceID=image_instance_id,
        Inactive=inactive,
        FormData={"k": "v"},
    )
    session.add(ann)
    session.flush()
    return ann


def test_list_active_excludes_inactive_and_filters_by_schema(session):
    """list_active drops Inactive rows and applies the form_schema_id filter."""
    keep = _make_annotation(session, "keep")
    _make_annotation(session, "gone", inactive=True)
    repo = FormAnnotationRepository(session, scope=admin_scope())

    rows = repo.list_active()
    ids = {r.FormAnnotationID for r in rows}
    assert keep.FormAnnotationID in ids
    assert all(not r.Inactive for r in rows)

    by_schema = repo.list_active(form_schema_id=keep.FormSchemaID)
    assert [r.FormAnnotationID for r in by_schema] == [keep.FormAnnotationID]

    assert repo.list_active(form_schema_id=999_999) == []


def test_get_with_tag_links_found_and_missing(session):
    """get_with_tag_links returns the row (tag links loaded) or None if absent."""
    ann = _make_annotation(session, "one")
    repo = FormAnnotationRepository(session, scope=admin_scope())

    got = repo.get_with_tag_links(ann.FormAnnotationID)
    assert got is not None and got.FormAnnotationID == ann.FormAnnotationID
    assert list(got.FormAnnotationTagLinks) == []  # eager-loaded, empty

    assert repo.get_with_tag_links(999_999) is None
