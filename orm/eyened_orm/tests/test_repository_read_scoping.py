"""An out-of-scope row reads as absent, so the existing NotFoundError 404s it."""
from __future__ import annotations

from datetime import date

import pytest

from eyened_orm.repositories import (
    ImageInstanceRepository,
    PatientRepository,
    StudyRepository,
)
from eyened_orm.utils.factories import (
    admin_scope,
    make_creator,
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
    scope_for,
)


@pytest.fixture()
def two_projects(session):
    """Project A and project B, one patient/study/series/image each."""
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    made = {}
    for name in ("A", "B"):
        project = make_project(session, name)
        patient = make_patient(session, project, f"pat-{name}")
        study = make_study(session, patient, date(2024, 1, 1))
        series = make_series(session, study)
        image = make_image(session, series, device, backend, f"img-{name}")
        made[name] = {
            "project": project.ProjectID,
            "patient": patient.PatientID,
            "study": study.StudyID,
            "series": series.SeriesID,
            "image": image.ImageInstanceID,
            "public_id": f"img-{name}",
        }
    session.commit()
    session.expunge_all()
    return made


def test_patient_read_returns_none_out_of_scope(session, two_projects):
    scope = scope_for(two_projects["A"]["project"])
    repo = PatientRepository(session, scope=scope)
    assert repo.get_with_attributes(two_projects["A"]["patient"]) is not None
    assert repo.get_with_attributes(two_projects["B"]["patient"]) is None


def test_study_read_returns_none_out_of_scope(session, two_projects):
    scope = scope_for(two_projects["A"]["project"])
    repo = StudyRepository(session, scope=scope)
    assert repo.get_by_id(two_projects["A"]["study"]) is not None
    assert repo.get_by_id(two_projects["B"]["study"]) is None


def test_image_reads_return_none_out_of_scope(session, two_projects):
    scope = scope_for(two_projects["A"]["project"])
    repo = ImageInstanceRepository(session, scope=scope)
    out_of_scope = two_projects["B"]
    assert repo.get_by_public_id(out_of_scope["public_id"]) is None
    assert repo.get_with_storage_by_public_id(out_of_scope["public_id"]) is None
    # The numeric-string form forces get_with_storage_by_public_id's PK-fallback
    # branch (PublicID lookup misses because it's a digit string, not "img-B").
    assert repo.get_with_storage_by_public_id(str(out_of_scope["image"])) is None
    assert (
        repo.get_full_graph_by_id(
            out_of_scope["image"],
            with_segmentations=False,
            with_form_annotations=False,
            with_model_segmentations=False,
        )
        is None
    )
    assert (
        repo.get_full_graph_by_public_id(
            out_of_scope["public_id"],
            with_segmentations=False,
            with_form_annotations=False,
            with_model_segmentations=False,
        )
        is None
    )


def test_the_numeric_fallback_is_scoped_too(session, two_projects):
    """get_full_graph_by_public_id falls back to the raw PK -- so must the filter."""
    scope = scope_for(two_projects["A"]["project"])
    repo = ImageInstanceRepository(session, scope=scope)
    assert (
        repo.get_full_graph_by_public_id(
            str(two_projects["B"]["image"]),
            with_segmentations=False,
            with_form_annotations=False,
            with_model_segmentations=False,
        )
        is None
    )


def test_an_identity_map_hit_does_not_bypass_the_filter(session, two_projects):
    """Session.get can answer from the identity map without querying at all."""
    from eyened_orm import ImageInstance

    session.get(ImageInstance, two_projects["B"]["image"])  # warm the identity map
    repo = ImageInstanceRepository(
        session, scope=scope_for(two_projects["A"]["project"])
    )
    assert (
        repo.get_full_graph_by_id(
            two_projects["B"]["image"],
            with_segmentations=False,
            with_form_annotations=False,
            with_model_segmentations=False,
        )
        is None
    )


def test_an_admin_scope_reads_everything(session, two_projects):
    repo = ImageInstanceRepository(session, scope=admin_scope())
    assert repo.get_by_public_id(two_projects["B"]["public_id"]) is not None


def test_a_tag_link_on_an_out_of_scope_row_reads_as_absent(session, two_projects):
    from eyened_orm import Tag
    from eyened_orm.tag import TagType

    creator = make_creator(session, "tag-creator")
    tag = Tag(
        TagName="t",
        TagType=TagType.ImageInstance,
        TagDescription="t",
        CreatorID=creator.CreatorID,
    )
    session.add(tag)
    session.flush()
    ImageInstanceRepository(session, scope=admin_scope()).add_link(
        tag_id=tag.TagID,
        image_instance_id=two_projects["B"]["image"],
        creator_id=creator.CreatorID,
        comment=None,
    )
    session.commit()

    repo = ImageInstanceRepository(
        session, scope=scope_for(two_projects["A"]["project"])
    )
    assert repo.get_tag_link(tag.TagID, two_projects["B"]["image"]) is None

    study_tag = Tag(
        TagName="st",
        TagType=TagType.Study,
        TagDescription="st",
        CreatorID=creator.CreatorID,
    )
    session.add(study_tag)
    session.flush()
    StudyRepository(session, scope=admin_scope()).add_link(
        tag_id=study_tag.TagID,
        study_id=two_projects["B"]["study"],
        creator_id=creator.CreatorID,
        comment=None,
    )
    session.commit()

    study_repo = StudyRepository(
        session, scope=scope_for(two_projects["A"]["project"])
    )
    assert study_repo.get_link(study_tag.TagID, two_projects["B"]["study"]) is None
