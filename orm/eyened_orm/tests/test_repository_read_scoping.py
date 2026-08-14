"""An out-of-scope row reads as absent, so the existing NotFoundError 404s it."""
from __future__ import annotations

from datetime import date

import pytest

from eyened_orm.repositories import (
    FormAnnotationRepository,
    ImageInstanceRepository,
    ModelSegmentationRepository,
    PatientRepository,
    SegmentationRepository,
    StudyRepository,
)
from eyened_orm.utils.factories import (
    admin_scope,
    make_creator,
    make_device,
    make_feature,
    make_form_annotation,
    make_form_schema,
    make_image,
    make_patient,
    make_project,
    make_segmentation,
    make_series,
    make_storage_backend,
    make_study,
    make_tag,
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
    # The owning scope still sees it. Without this direction the test passes for
    # a predicate that hides the link from EVERYONE: tagging then reads as
    # untagged, so DELETE silently no-ops and a re-tag hits the duplicate
    # composite key as a 500.
    owner_repo = ImageInstanceRepository(
        session, scope=scope_for(two_projects["B"]["project"])
    )
    assert owner_repo.get_tag_link(tag.TagID, two_projects["B"]["image"]) is not None

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
    owner_study_repo = StudyRepository(
        session, scope=scope_for(two_projects["B"]["project"])
    )
    assert (
        owner_study_repo.get_link(study_tag.TagID, two_projects["B"]["study"])
        is not None
    )


def test_scoped_one_refuses_an_entity_with_no_scoping_rule(session):
    """A helper named `scoped_one` that quietly filters nothing is a trap.

    Tag has no project anchor, so apply_scope passes it through untouched --
    correct for apply_scope, wrong for this helper. SubTaskImageLink is the
    live case: it is in neither registry, and the first task to read it under a
    scope would otherwise get a green no-op.
    """
    from eyened_orm import Tag

    from eyened_orm.repositories._scoped import scoped_one

    with pytest.raises(KeyError, match="no scoping rule"):
        scoped_one(session, Tag, admin_scope(), Tag.TagID == 1)


def _image_of(session, two_projects, key):
    from eyened_orm import ImageInstance

    return session.get(ImageInstance, two_projects[key]["image"])


def _patient_of(session, two_projects, key):
    from eyened_orm import Patient

    return session.get(Patient, two_projects[key]["patient"])


def test_segmentation_reads_are_scoped_by_their_image(session, two_projects):
    """A segmentation is visible exactly to the projects of the image it annotates."""
    from eyened_orm.tag import TagType

    creator = make_creator(session, "alice")
    feature = make_feature(session, "retina")
    seg_a = make_segmentation(
        session, _image_of(session, two_projects, "A"), feature, creator
    )
    seg_b = make_segmentation(
        session, _image_of(session, two_projects, "B"), feature, creator
    )
    a_id, b_id = seg_a.SegmentationID, seg_b.SegmentationID
    session.commit()

    repo = SegmentationRepository(
        session, scope=scope_for(two_projects["A"]["project"])
    )
    assert repo.get_by_id(a_id) is not None
    assert repo.get_by_id(b_id) is None
    assert repo.get_with_tag_links(b_id) is None
    # Positive control: the predicate hides B from A, not from everyone.
    owner = SegmentationRepository(
        session, scope=scope_for(two_projects["B"]["project"])
    )
    assert owner.get_by_id(b_id) is not None
    assert owner.get_with_tag_links(b_id) is not None

    tag = make_tag(session, "seg-tag", TagType.Segmentation, creator)
    SegmentationRepository(session, scope=admin_scope()).add_link(
        tag_id=tag.TagID, segmentation_id=b_id, creator_id=creator.CreatorID
    )
    session.commit()

    assert repo.get_tag_link(tag.TagID, b_id) is None
    # The owning scope still sees it. Without this direction the test passes
    # for a predicate that hides the link from EVERYONE, not just from A.
    assert owner.get_tag_link(tag.TagID, b_id) is not None


def test_model_segmentation_reads_are_scoped_by_their_own_entity(session, two_projects):
    """ModelSegmentation is a distinct mapped class from Segmentation.

    apply_scope keys on the class it is handed and BOTH are registered, so
    passing `Segmentation` here still filters -- by the wrong join chain -- and
    scoped_one's registry check cannot see it. This test is the only thing that
    can.
    """
    from eyened_orm import ModelSegmentation
    from eyened_orm.segmentation import DataRepresentation, Datatype, SegmentationModel

    # No factory exists: ModelSegmentation.ModelID is NOT NULL and SegmentationModel
    # is a joined-table subclass of Model, whose ModelName/Version are NOT NULL.
    model = SegmentationModel(ModelName="m", Version="1")
    session.add(model)
    session.flush()
    made = {}
    for key in ("A", "B"):
        row = ModelSegmentation(
            ModelID=model.ModelID,
            ImageInstanceID=two_projects[key]["image"],
            DataType=Datatype.R8UI,
            DataRepresentation=DataRepresentation.Binary,
            Depth=1,
            Height=4,
            Width=4,
        )
        session.add(row)
        session.flush()
        made[key] = row.ModelSegmentationID
    session.commit()

    repo = ModelSegmentationRepository(
        session, scope=scope_for(two_projects["A"]["project"])
    )
    assert repo.get_by_id(made["A"]) is not None
    assert repo.get_by_id(made["B"]) is None
    owner = ModelSegmentationRepository(
        session, scope=scope_for(two_projects["B"]["project"])
    )
    assert owner.get_by_id(made["B"]) is not None


def test_form_annotation_reads_are_scoped_by_their_patient(session, two_projects):
    """A form annotation is visible exactly to the projects of its patient."""
    from eyened_orm.tag import TagType

    creator = make_creator(session, "alice")
    schema = make_form_schema(session, "s")
    made = {
        key: make_form_annotation(
            session, schema, _patient_of(session, two_projects, key), creator
        ).FormAnnotationID
        for key in ("A", "B")
    }
    session.commit()

    repo = FormAnnotationRepository(
        session, scope=scope_for(two_projects["A"]["project"])
    )
    assert repo.get_by_id(made["A"]) is not None
    assert repo.get_by_id(made["B"]) is None
    assert repo.get_with_tag_links(made["B"]) is None
    owner = FormAnnotationRepository(
        session, scope=scope_for(two_projects["B"]["project"])
    )
    assert owner.get_by_id(made["B"]) is not None

    tag = make_tag(session, "form-tag", TagType.FormAnnotation, creator)
    FormAnnotationRepository(session, scope=admin_scope()).add_link(
        tag_id=tag.TagID,
        form_annotation_id=made["B"],
        creator_id=creator.CreatorID,
        comment=None,
    )
    session.commit()

    assert repo.get_tag_link(tag.TagID, made["B"]) is None
    # The owning scope still sees it. Without this direction the test passes
    # for a predicate that hides the link from EVERYONE, not just from A.
    assert owner.get_tag_link(tag.TagID, made["B"]) is not None


def test_list_active_returns_only_in_scope_rows(session, two_projects):
    """A collection filters and returns 200; it never 404s."""
    creator = make_creator(session, "alice")
    schema = make_form_schema(session, "s")
    for key in ("A", "B"):
        make_form_annotation(
            session, schema, _patient_of(session, two_projects, key), creator
        )
    session.commit()

    a_rows = FormAnnotationRepository(
        session, scope=scope_for(two_projects["A"]["project"])
    ).list_active()
    assert {r.PatientID for r in a_rows} == {two_projects["A"]["patient"]}
    b_rows = FormAnnotationRepository(
        session, scope=scope_for(two_projects["B"]["project"])
    ).list_active()
    assert {r.PatientID for r in b_rows} == {two_projects["B"]["patient"]}


def _feature_with_segmentations_in_both_projects(session, two_projects):
    """One segmentation on A's image, two on B's, all on one feature.

    Asymmetric counts on purpose: with one each, a filter that returns the
    *other* project's rows produces the same number as a correct one.
    """
    from eyened_orm import ImageInstance

    creator = make_creator(session, "counter")
    feature = make_feature(session, "counted")
    for key, how_many in (("A", 1), ("B", 2)):
        image = session.get(ImageInstance, two_projects[key]["image"])
        for _ in range(how_many):
            make_segmentation(session, image, feature, creator)
    feature_id = feature.FeatureID
    session.commit()
    session.expunge_all()
    return feature_id


def test_segmentation_counts_are_scoped(session, two_projects):
    """A member of one project is told its own volume, not the whole database.

    ``Segmentation`` is a ``SINGLE_PROJECT_ENTITIES`` member, so an unscoped
    ``func.count()`` over it hands any authenticated caller -- including one
    with no memberships -- annotation-activity volume for every project.
    """
    from eyened_orm.repositories.feature_repository import FeatureRepository

    feature_id = _feature_with_segmentations_in_both_projects(session, two_projects)

    a_repo = FeatureRepository(session, scope=scope_for(two_projects["A"]["project"]))
    b_repo = FeatureRepository(session, scope=scope_for(two_projects["B"]["project"]))

    assert a_repo.segmentation_counts() == {feature_id: 1}
    assert b_repo.segmentation_counts() == {feature_id: 2}
    assert FeatureRepository(session, scope=admin_scope()).segmentation_counts() == {
        feature_id: 3
    }


def test_count_segmentations_is_deliberately_global(session, two_projects):
    """The single-feature count does **not** follow the grouped one, by design.

    ``count_segmentations`` is the referential-integrity guard behind the
    delete-conflict check, not display data. Scoped, a feature still
    referenced from a project the caller cannot reach counts 0, the 409 never
    fires, and the delete dies at the flush as an unmapped ``IntegrityError``
    -- a correct refusal replaced by a 500. It therefore reads every
    referencing row, and the *message* built on it carries no number (see
    ``server/services/feature_service.py``), which is what keeps the count
    from leaking.

    The last assertion is the point of putting both methods in one test: its
    scoped sibling must stay scoped on this very same seed, so a future edit
    cannot revert the two together in either direction and stay green.
    """
    from eyened_orm.repositories.feature_repository import FeatureRepository

    feature_id = _feature_with_segmentations_in_both_projects(session, two_projects)

    a_repo = FeatureRepository(session, scope=scope_for(two_projects["A"]["project"]))
    b_repo = FeatureRepository(session, scope=scope_for(two_projects["B"]["project"]))

    assert a_repo.count_segmentations(feature_id) == 3
    assert b_repo.count_segmentations(feature_id) == 3
    assert (
        FeatureRepository(session, scope=admin_scope()).count_segmentations(feature_id)
        == 3
    )

    assert a_repo.segmentation_counts() == {feature_id: 1}
