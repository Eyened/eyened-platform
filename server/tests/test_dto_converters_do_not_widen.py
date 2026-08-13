"""What the six database-reading DTO converters actually return.

``test_repository_reads_are_scoped.py`` pins their *names* -- ``_DTO_SESSION_TOUCHES``
is an exact set, so a seventh converter that starts reading, or a rename of one
of these six, turns that guard red. It observes nothing about what any of them
returns: replacing ``_get_public_id_for_instance_id``'s body with
``return "leaked-public-id"`` left the whole suite green.

This file is the behavioural half, and it is *in addition* to that pin, not
instead of it. Every converter here reads through a raw ``Session`` with no
scope in the chain, so the property that keeps them honest is not filtering --
it is that each resolves only identifiers already carried by the row it was
handed. So every test seeds a second project the caller cannot reach, converts
a row from the first, and asserts twice:

- the resolved identifier equals the in-reach image's PublicID exactly, which
  is what catches a converter fabricating or substituting a value; and
- the out-of-reach PublicID appears nowhere in the serialized output, which is
  what catches a converter widening its read.

An absence assertion alone would pass for a converter that returned a constant,
and an equality assertion alone would pass for one that returned the right
value *and* extra rows. Both are needed.

Not a claim that these converters are scoped. They are not, and
``_DTO_SESSION_TOUCHES`` says so; routing them through a scoped repository is
the long-term answer and is out of scope here.
"""
from __future__ import annotations

from datetime import date

import pytest
from eyened_orm import ModelSegmentation
from eyened_orm.segmentation import DataRepresentation, Datatype, SegmentationModel
from eyened_orm.utils.factories import (
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
)

from server.dtos.dto_converter import DTOConverter

# Distinctive on purpose: every absence assertion below is a substring search
# over serialized JSON, and a PublicID like "img-b" would also match "img-b2".
_OUT_OF_REACH = "OUT-OF-REACH-PUBLIC-ID"
_IN_REACH = "in-reach-public-id"


@pytest.fixture()
def two_projects(session):
    """Project A (converted from) and project B (out of reach), each with an image.

    B holds a full patient/study/series/image chain rather than a bare row, so
    a converter that widened its read would have something real to find. Ids
    are read out before the commit: ``expire_on_commit=True``.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    creator = make_creator(session, "grader")

    project_a = make_project(session, "A")
    patient_a = make_patient(session, project_a, "pat-a")
    study_a = make_study(session, patient_a, date(2024, 1, 1))
    image_a = make_image(
        session, device=device, backend=backend, series=make_series(session, study_a),
        public_id=_IN_REACH,
    )

    project_b = make_project(session, "B")
    patient_b = make_patient(session, project_b, "pat-b")
    study_b = make_study(session, patient_b, date(2024, 1, 1))
    image_b = make_image(
        session, device=device, backend=backend, series=make_series(session, study_b),
        public_id=_OUT_OF_REACH,
    )

    return {
        "creator": creator,
        "patient_a": patient_a,
        "study_a": study_a,
        "image_a": image_a,
        "image_a_id": image_a.ImageInstanceID,
        "patient_b": patient_b,
        "image_b": image_b,
        "image_b_id": image_b.ImageInstanceID,
    }


def _dumped(dto) -> str:
    """The DTO as JSON text, for the "nowhere in the output" half of each test."""
    return dto.model_dump_json()


def test_get_public_id_for_instance_id_resolves_exactly_the_id_it_is_given(
    session, two_projects
):
    """The helper every other converter falls back to, pinned by value.

    Unscoped by construction -- hand it an out-of-reach id and it resolves it,
    which is exactly why containment has to live in the caller and why this
    function is on ``_DTO_SESSION_TOUCHES``. What IS pinned here is that it
    answers for the id it was given and for no other, and that a missing row
    gives None rather than something plausible.
    """
    resolve = DTOConverter._get_public_id_for_instance_id

    assert resolve(session, two_projects["image_a_id"]) == _IN_REACH
    assert resolve(session, 9_999_999) is None
    assert resolve(session, None) is None
    assert resolve(None, two_projects["image_a_id"]) is None


def test_registration_ids_resolve_only_the_ids_named_in_the_json(
    session, two_projects
):
    """Legacy ImageInstanceID -> PublicID widening stays inside the given edges."""
    transforms = [
        {
            "image1": two_projects["image_a_id"],
            "image2": two_projects["image_a_id"],
            "type": "ProjectiveTransform",
        }
    ]

    out = DTOConverter._registration_attr_to_public_ids(session, transforms)

    assert [(e["image1"], e["image2"]) for e in out] == [(_IN_REACH, _IN_REACH)]
    assert _OUT_OF_REACH not in str(out)


def test_patient_detail_widens_only_its_own_registration_ids(session, two_projects):
    """The one converter whose honest exposure the pin calls out by name.

    It widens Registration JSON already stored on the patient being converted,
    so the test seeds a real Registration value rather than asserting an
    absence over a patient with no attributes -- which would pass without the
    widening code ever running. The edge names project A's image only; project
    B's image is seeded and must not appear, and neither must project B itself.

    Patient B gets a Registration of its own, naming image B. Without it the
    absence assertion would hold for a converter that read every
    AttributeValue in the database, because there would be nothing else to
    read -- the seeded row is what makes "did not widen" mean something.
    """
    from eyened_orm.attributes import (
        AttributeDataType,
        AttributeDefinition,
        AttributeValue,
    )

    definition = AttributeDefinition(
        AttributeName="Registration", AttributeDataType=AttributeDataType.JSON
    )
    session.add(definition)
    session.flush()
    for patient, image_id in (
        (two_projects["patient_a"], two_projects["image_a_id"]),
        (two_projects["patient_b"], two_projects["image_b_id"]),
    ):
        value = AttributeValue(
            AttributeID=definition.AttributeID, PatientID=patient.PatientID
        )
        value.AttributeDefinition = definition
        value.value = [
            {
                "image1": image_id,
                "image2": image_id,
                "type": "ProjectiveTransform",
            }
        ]
        session.add(value)
    session.flush()

    dto = DTOConverter.patient_to_detail_get(two_projects["patient_a"])

    edges = dto.attrs["Registration"][0].value
    assert [(e["image1"], e["image2"]) for e in edges] == [(_IN_REACH, _IN_REACH)]
    assert dto.identifier == "pat-a"
    assert dto.project.name == "A"
    assert _OUT_OF_REACH not in _dumped(dto)
    assert '"B"' not in _dumped(dto)


def test_segmentation_get_carries_its_own_images_public_id(session, two_projects):
    seg = make_segmentation(
        session,
        two_projects["image_a"],
        make_feature(session, "f"),
        two_projects["creator"],
    )

    dto = DTOConverter.segmentation_to_get(seg)

    assert dto.image_id == _IN_REACH
    assert _OUT_OF_REACH not in _dumped(dto)


def test_model_segmentation_get_carries_its_own_images_public_id(
    session, two_projects
):
    model = SegmentationModel(ModelName="m", Version="1")
    session.add(model)
    session.flush()
    ms = ModelSegmentation(
        ModelID=model.ModelID,
        ImageInstanceID=two_projects["image_a_id"],
        DataType=Datatype.R8UI,
        DataRepresentation=DataRepresentation.Binary,
        Depth=1,
        Height=4,
        Width=4,
    )
    session.add(ms)
    session.flush()

    dto = DTOConverter.model_segmentation_to_get(ms)

    assert dto.image_id == _IN_REACH
    assert _OUT_OF_REACH not in _dumped(dto)


def test_form_annotation_get_carries_its_own_images_public_id(session, two_projects):
    annotation = make_form_annotation(
        session,
        make_form_schema(session, "s"),
        two_projects["patient_a"],
        two_projects["creator"],
        image=two_projects["image_a"],
    )

    dto = DTOConverter.form_annotation_to_get(annotation)

    assert dto.image_id == _IN_REACH
    assert dto.object_type == "image_instance"
    assert _OUT_OF_REACH not in _dumped(dto)
