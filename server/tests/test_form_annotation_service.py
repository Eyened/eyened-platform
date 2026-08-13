import pytest
from datetime import date
from types import SimpleNamespace

from eyened_orm import (
    Creator,
    DeviceInstance,
    DeviceModel,
    FormAnnotation,
    FormSchema,
    ImageInstance,
    Patient,
    Project,
    Series,
    Study,
    Tag,
)
from eyened_orm.project import ExternalEnum
from eyened_orm.tag import TagType
from eyened_orm.repositories.form_annotation_repository import (
    FormAnnotationRepository,
)
from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.tag_repository import TagRepository

from server.services.acting_user import ActingUser
from server.services.exceptions import BadRequestError, NotFoundError
from server.services.form_annotation_service import FormAnnotationService
from eyened_orm.authz.errors import NotVisibleError
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.utils.factories import admin_scope, scope_for


class FakeAudit:
    """Records .record() calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


def _service(
    session, actor: ActingUser | None = None, *, audit=None
) -> FormAnnotationService:
    scope = (
        admin_scope(actor_id=actor.id, username=actor.username)
        if actor is not None
        else admin_scope()
    )
    return FormAnnotationService(
        FormAnnotationRepository(session, scope=scope),
        ImageInstanceRepository(session, scope=scope),
        TagRepository(session, scope=scope),
        scope=scope,
        audit=audit,
    )


def _make_patient_and_schema(session, key: str) -> tuple[int, int]:
    """Create a Project/Patient + FormSchema; return (patient_id, schema_id)."""
    project = Project(ProjectName=f"P-{key}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"ID-{key}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    schema = FormSchema(SchemaName=f"S-{key}")
    session.add(schema)
    session.flush()
    return patient.PatientID, schema.FormSchemaID


def _make_annotation(session, key: str, *, inactive: bool = False) -> FormAnnotation:
    """Create a minimal active/inactive FormAnnotation; return the row."""
    patient_id, schema_id = _make_patient_and_schema(session, key)
    creator = Creator(CreatorName=f"c-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    ann = FormAnnotation(
        FormSchemaID=schema_id,
        PatientID=patient_id,
        CreatorID=creator.CreatorID,
        Inactive=inactive,
        FormData={"answer": 1},
    )
    session.add(ann)
    session.flush()
    return ann


def _make_image(session, public_id: str) -> int:
    """Build the minimal graph an ImageInstance FK-requires; return its id."""
    project = Project(ProjectName=f"IP-{public_id}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"IID-{public_id}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=date.today())
    session.add(study)
    session.flush()
    series = Series(StudyID=study.StudyID)
    session.add(series)
    session.flush()
    model = DeviceModel(Manufacturer="Mf", ManufacturerModelName="M")
    session.add(model)
    session.flush()
    device = DeviceInstance(DeviceModelID=model.DeviceModelID, Description="d")
    session.add(device)
    session.flush()
    image = ImageInstance(
        PublicID=public_id,
        SeriesID=series.SeriesID,
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier=f"ds-{public_id}",
    )
    session.add(image)
    session.flush()
    return image.ImageInstanceID


def _actor(session, key: str = "actor") -> ActingUser:
    creator = Creator(CreatorName=f"u-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    return ActingUser(id=creator.CreatorID, username=creator.CreatorName)


def _author(annotation) -> ActingUser:
    """The acting user for a *modify* of ``annotation``: its own author.

    ``_make_annotation`` mints its own ``c-<key>`` creator, so ``_actor``'s
    unrelated ``u-actor`` is a different user -- and the ownership overlay
    refuses a modify by anyone else, administrators included. A test about
    audit content or data behaviour must therefore act as the author, or it
    stops testing what its name says and starts testing the overlay.
    """
    return ActingUser(
        id=annotation.CreatorID, username=annotation.Creator.CreatorName
    )


def _make_tag(session, creator_id: int, tag_type: TagType = TagType.FormAnnotation) -> Tag:
    tag = Tag(
        TagName=f"t-{tag_type.name}-{creator_id}",
        TagDescription="d",
        TagType=tag_type,
        CreatorID=creator_id,
    )
    session.add(tag)
    session.flush()
    return tag


def test_list_annotations_excludes_inactive(session):
    """list_annotations returns only active rows (no image_id filter)."""
    keep = _make_annotation(session, "keep")
    _make_annotation(session, "gone", inactive=True)

    rows = _service(session).list_annotations(
        patient_id=None,
        study_id=None,
        image_id=None,
        form_schema_id=None,
        sub_task_id=None,
    )

    ids = {r.FormAnnotationID for r in rows}
    assert keep.FormAnnotationID in ids
    assert all(not r.Inactive for r in rows)


def test_list_annotations_unknown_image_id_raises_not_found(session):
    """An image_id filter that resolves to nothing raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).list_annotations(
            patient_id=None,
            study_id=None,
            image_id="no-such-image",
            form_schema_id=None,
            sub_task_id=None,
        )


def test_get_annotation_unknown_raises_not_found(session):
    """Getting a missing annotation is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).get_annotation(999_999)


def test_get_value_unknown_raises_not_found(session):
    """get_value on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).get_value(999_999)


def test_create_resolves_image_and_persists(session):
    """create resolves image_id and persists the row."""
    actor = _actor(session)
    patient_id, schema_id = _make_patient_and_schema(session, "c1")
    image_id = _make_image(session, "img-1")

    ann = _service(session, actor=actor).create(
        form_schema_id=schema_id,
        patient_id=patient_id,
        study_id=None,
        image_id="img-1",
        laterality=None,
        sub_task_id=None,
        form_data={"a": 1},
        form_annotation_reference_id=None,
    )

    assert ann.FormAnnotationID is not None
    assert ann.ImageInstanceID == image_id


def test_create_unknown_image_raises_not_found(session):
    """create with an unresolvable image_id raises NotFoundError (-> 404)."""
    actor = _actor(session)
    patient_id, schema_id = _make_patient_and_schema(session, "c2")
    with pytest.raises(NotFoundError):
        _service(session, actor=actor).create(
            form_schema_id=schema_id,
            patient_id=patient_id,
            study_id=None,
            image_id="no-image",
            laterality=None,
            sub_task_id=None,
            form_data=None,
            form_annotation_reference_id=None,
        )


def test_create_logs_insert(session):
    """Creating an annotation emits one INSERT audit record naming the entity."""
    actor = _actor(session)
    patient_id, schema_id = _make_patient_and_schema(session, "ci1")
    audit = FakeAudit()

    ann = _service(session, actor, audit=audit).create(
        form_schema_id=schema_id,
        patient_id=patient_id,
        study_id=None,
        image_id=None,
        laterality=None,
        sub_task_id=None,
        form_data={"a": 1},
        form_annotation_reference_id=None,
    )

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "INSERT"
    assert rec["entity"] == "FormAnnotation"
    assert rec["entity_id"] == ann.FormAnnotationID
    assert rec["actor"] == actor


def test_update_applies_field(session):
    """update applies a provided field to the annotation."""
    ann = _make_annotation(session, "u1")
    actor = _author(ann)

    updated = _service(session, actor=actor).update(
        ann.FormAnnotationID, {"form_data": {"b": 2}}
    )

    assert updated.FormData == {"b": 2}


def test_update_unknown_raises_not_found(session):
    """update on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).update(999_999, {"form_data": {}})


def test_update_logs_diff_with_applied_columns(session):
    """update's UPDATE audit carries a true {old, new} diff keyed by the
    PascalCase column actually set (FormData) — the sanctioned removal of the
    pre-refactor 'None -> <new>' quirk (Decision #3: the old snake_case
    getattr never matched the PascalCase column, so every entry read
    'None -> <new>' regardless of the real old value)."""
    ann = _make_annotation(session, "ud1")
    actor = _author(ann)
    audit = FakeAudit()

    _service(session, actor, audit=audit).update(
        ann.FormAnnotationID, {"form_data": {"b": 2}}
    )

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "FormAnnotation"
    assert rec["entity_id"] == ann.FormAnnotationID
    assert rec["changes"] == {"FormData": {"old": {"answer": 1}, "new": {"b": 2}}}


def test_update_image_id_diffs_on_image_instance_id_column(session):
    """An image_id update diffs the ImageInstanceID column it actually set
    (via the same snake->Pascal map used to setattr), not the snake_case
    'image_id' request key — the other half of the Decision-3 removal."""
    ann = _make_annotation(session, "ud2")
    actor = _author(ann)
    image_id = _make_image(session, "img-2")
    audit = FakeAudit()

    _service(session, actor, audit=audit).update(
        ann.FormAnnotationID, {"image_id": "img-2"}
    )

    assert audit.records[0]["changes"] == {
        "ImageInstanceID": {"old": None, "new": image_id}
    }


def test_soft_delete_sets_inactive(session):
    """soft_delete flags the row Inactive."""
    actor = _actor(session)
    ann = _make_annotation(session, "d1")

    _service(session, actor=actor).soft_delete(ann.FormAnnotationID)

    assert ann.Inactive is True


def test_soft_delete_unknown_raises_not_found(session):
    """soft_delete on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).soft_delete(999_999)


def test_soft_delete_logs_delete(session):
    """soft_delete's DELETE audit carries a snapshot of the annotation's fields."""
    actor = _actor(session)
    ann = _make_annotation(session, "sd1")
    audit = FakeAudit()

    _service(session, actor, audit=audit).soft_delete(ann.FormAnnotationID)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "DELETE"
    assert rec["entity"] == "FormAnnotation"
    assert rec["entity_id"] == ann.FormAnnotationID
    assert rec["changes"]["patient_id"] == ann.PatientID


def test_set_value_overwrites_form_data(session):
    """set_value overwrites the annotation's FormData payload."""
    ann = _make_annotation(session, "v1")
    actor = _author(ann)

    _service(session, actor=actor).set_value(ann.FormAnnotationID, {"new": 9})

    assert ann.FormData == {"new": 9}


def test_set_value_unknown_raises_not_found(session):
    """set_value on a missing annotation raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service(session).set_value(999_999, {})


def test_set_value_logs_update_without_changes(session):
    """set_value's UPDATE audit carries no changes payload — pre-refactor
    log_simple never included field detail for this high-frequency op;
    preserved as-is (not a Decision-3-style improvement site)."""
    ann = _make_annotation(session, "sv1")
    actor = _author(ann)
    audit = FakeAudit()

    _service(session, actor, audit=audit).set_value(ann.FormAnnotationID, {"x": 1})

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "FormAnnotation"
    assert rec["entity_id"] == ann.FormAnnotationID
    assert rec.get("changes") is None


def test_tag_creates_link(session):
    """tag links a FormAnnotation tag and returns the link."""
    actor = _actor(session)
    ann = _make_annotation(session, "t1")
    tag = _make_tag(session, actor.id)

    link = _service(session, actor=actor).tag(ann.FormAnnotationID, tag.TagID, "hi")

    assert link.TagID == tag.TagID
    assert link.Comment == "hi"
    assert link.Tag.TagID == tag.TagID


def test_tag_unknown_annotation_raises_not_found(session):
    """tag on a missing annotation is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    tag = _make_tag(session, actor.id)
    with pytest.raises(NotFoundError):
        _service(session, actor=actor).tag(999_999, tag.TagID, None)


def test_tag_unknown_tag_raises_not_found(session):
    """tag with an unknown tag id is translated to NotFoundError (-> 404)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t2")
    with pytest.raises(NotFoundError):
        _service(session, actor=actor).tag(ann.FormAnnotationID, 999_999, None)


def test_tag_wrong_type_raises_bad_request(session):
    """tag with a non-FormAnnotation tag raises BadRequestError (-> 400)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t3")
    tag = _make_tag(session, actor.id, tag_type=TagType.ImageInstance)
    with pytest.raises(BadRequestError):
        _service(session, actor=actor).tag(ann.FormAnnotationID, tag.TagID, None)


def test_tag_existing_updates_comment(session):
    """A second tag with a comment updates the existing link, not duplicates."""
    actor = _actor(session)
    ann = _make_annotation(session, "t4")
    tag = _make_tag(session, actor.id)
    service = _service(session, actor=actor)

    service.tag(ann.FormAnnotationID, tag.TagID, "first")
    link = service.tag(ann.FormAnnotationID, tag.TagID, "second")

    assert link.Comment == "second"


def test_tag_logs_insert(session):
    """tag's INSERT audit carries the link identity + comment."""
    actor = _actor(session)
    ann = _make_annotation(session, "ti1")
    tag = _make_tag(session, actor.id)
    audit = FakeAudit()

    _service(session, actor, audit=audit).tag(ann.FormAnnotationID, tag.TagID, "hi")

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "INSERT"
    assert rec["entity"] == "FormAnnotationTagLink"
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "form_annotation_id": ann.FormAnnotationID,
        "comment": "hi",
    }


def test_tag_update_logs_diff_with_identity(session):
    """A re-tag comment UPDATE (via tag()) folds the (tag_id,
    form_annotation_id) identity into changes alongside the Comment diff.
    FormAnnotationTagLink has a composite PK, so entity_id is null; identity
    must live in changes (matches the INSERT above and untag's DELETE below)
    or the audit row is unidentifiable."""
    actor = _actor(session)
    ann = _make_annotation(session, "ti2")
    tag = _make_tag(session, actor.id)
    _service(session, actor=actor).tag(ann.FormAnnotationID, tag.TagID, "first")
    audit = FakeAudit()

    _service(session, actor, audit=audit).tag(ann.FormAnnotationID, tag.TagID, "second")

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "FormAnnotationTagLink"
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "form_annotation_id": ann.FormAnnotationID,
        "Comment": {"old": "first", "new": "second"},
    }


def test_patch_tag_updates_comment(session):
    """patch_tag overwrites the comment on an existing link."""
    actor = _actor(session)
    ann = _make_annotation(session, "t5")
    tag = _make_tag(session, actor.id)
    service = _service(session, actor=actor)
    service.tag(ann.FormAnnotationID, tag.TagID, "old")

    link = service.patch_tag(ann.FormAnnotationID, tag.TagID, "new")

    assert link.Comment == "new"


def test_patch_tag_unknown_link_raises_not_found(session):
    """patch_tag with no existing link raises NotFoundError (-> 404)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t6")
    tag = _make_tag(session, actor.id)
    with pytest.raises(NotFoundError):
        _service(session, actor=actor).patch_tag(ann.FormAnnotationID, tag.TagID, "x")


def test_patch_tag_logs_update_as_diff(session):
    """patch_tag's UPDATE folds the same (tag_id, form_annotation_id) identity
    into changes alongside the Comment diff. Separate code path from tag()'s
    re-tag branch above — must be verified independently."""
    actor = _actor(session)
    ann = _make_annotation(session, "pt1")
    tag = _make_tag(session, actor.id)
    _service(session, actor=actor).tag(ann.FormAnnotationID, tag.TagID, "old")
    audit = FakeAudit()

    _service(session, actor, audit=audit).patch_tag(ann.FormAnnotationID, tag.TagID, "new")

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "UPDATE"
    assert rec["entity"] == "FormAnnotationTagLink"
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "form_annotation_id": ann.FormAnnotationID,
        "Comment": {"old": "old", "new": "new"},
    }


def test_untag_removes_link(session):
    """untag deletes the link for that (annotation, tag)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t7")
    tag = _make_tag(session, actor.id)
    service = _service(session, actor=actor)
    service.tag(ann.FormAnnotationID, tag.TagID, None)

    service.untag(ann.FormAnnotationID, tag.TagID)

    assert (
        FormAnnotationRepository(session, scope=admin_scope()).get_tag_link(
            tag.TagID, ann.FormAnnotationID
        )
        is None
    )


def test_untag_absent_link_is_idempotent(session):
    """untag with no link present is a no-op (no error)."""
    actor = _actor(session)
    ann = _make_annotation(session, "t8")
    tag = _make_tag(session, actor.id)

    # Does not raise even though no link exists.
    _service(session, actor=actor).untag(ann.FormAnnotationID, tag.TagID)


def test_untag_logs_delete(session):
    """untag's DELETE audit carries the removed link's identity + data."""
    actor = _actor(session)
    ann = _make_annotation(session, "ut1")
    tag = _make_tag(session, actor.id)
    _service(session, actor=actor).tag(ann.FormAnnotationID, tag.TagID, "bye")
    audit = FakeAudit()

    _service(session, actor, audit=audit).untag(ann.FormAnnotationID, tag.TagID)

    assert len(audit.records) == 1
    rec = audit.records[0]
    assert rec["action"] == "DELETE"
    assert rec["entity"] == "FormAnnotationTagLink"
    assert rec["changes"] == {
        "tag_id": tag.TagID,
        "form_annotation_id": ann.FormAnnotationID,
        "comment": "bye",
        "creator_id": actor.id,
    }


def _scoped_service(session, scope) -> FormAnnotationService:
    return FormAnnotationService(
        FormAnnotationRepository(session, scope=scope),
        ImageInstanceRepository(session, scope=scope),
        TagRepository(session, scope=scope),
        scope=scope,
        audit=None,
    )


def _annotation_across_two_projects(session):
    """An annotation anchored in project A, plus a patient in project B.

    The destination is the point: ``update`` resolves the annotation's projects
    as they are *now*, so a re-anchor is a write into a project the check never
    named.
    """
    from eyened_orm.utils.factories import (
        make_creator,
        make_form_annotation,
        make_form_schema,
        make_patient,
        make_project,
    )

    project_a = make_project(session, "move-A")
    project_b = make_project(session, "move-B")
    patient_a = make_patient(session, project_a, "pat-move-A")
    patient_b = make_patient(session, project_b, "pat-move-B")
    schema = make_form_schema(session, "move-schema")
    author = make_creator(session, "move-author")
    annotation = make_form_annotation(session, schema, patient_a, author)

    ids = SimpleNamespace(
        project_a=project_a.ProjectID,
        project_b=project_b.ProjectID,
        patient_a=patient_a.PatientID,
        patient_b=patient_b.PatientID,
        author=author.CreatorID,
        annotation=annotation.FormAnnotationID,
    )
    session.commit()
    session.expunge_all()
    return ids


def test_update_refuses_to_re_anchor_an_annotation_into_an_unreachable_project(session):
    """A grader in A only cannot move their own annotation to a patient in B."""
    ids = _annotation_across_two_projects(session)
    scope = scope_for(ids.project_a, role=ProjectRole.grader, actor_id=ids.author)

    with pytest.raises(NotVisibleError):
        _scoped_service(session, scope).update(
            ids.annotation, {"patient_id": ids.patient_b}
        )

    # Read back through the identity map deliberately: a check that ran *after*
    # the setattr would leave the new value on the in-session row, and a fresh
    # read after an expunge would not see it.
    assert session.get(FormAnnotation, ids.annotation).PatientID == ids.patient_a


def test_update_allows_a_re_anchor_between_two_projects_the_caller_holds(session):
    """The check is the union of before and after, not a ban on re-anchoring."""
    ids = _annotation_across_two_projects(session)
    scope = scope_for(
        ids.project_a, ids.project_b, role=ProjectRole.grader, actor_id=ids.author
    )

    _scoped_service(session, scope).update(
        ids.annotation, {"patient_id": ids.patient_b}
    )

    session.commit()
    session.expunge_all()
    assert session.get(FormAnnotation, ids.annotation).PatientID == ids.patient_b


def _cross_anchored_annotations(session):
    """Two annotations anchored in project B, one pointing at project A's image.

    The mis-scoped shape is real -- 15 such ``FormAnnotation`` rows exist in
    production, where ``PatientID`` and ``ImageInstanceID`` disagree about
    which project the row belongs to. The annotation is anchored on
    ``PatientID``, so a grader in B legitimately reaches it; the image it
    names is not theirs to know about.

    The in-scope twin is what makes the assertion mean "out of reach" rather
    than "``image_id`` stopped being emitted at all".
    """
    from eyened_orm.utils.factories import (
        make_creator,
        make_device,
        make_image,
        make_patient,
        make_project,
        make_series,
        make_storage_backend,
        make_study,
    )

    backend = make_storage_backend(session)
    device = make_device(session, "leak")
    creator = make_creator(session, "leak-c")
    schema = FormSchema(SchemaName="S-leak")
    session.add(schema)
    session.flush()

    images = {}
    patients = {}
    for name in ("A", "B"):
        project = make_project(session, f"leak-{name}")
        patient = make_patient(session, project, f"pat-leak-{name}")
        study = make_study(session, patient, date(2024, 1, 1))
        series = make_series(session, study)
        images[name] = make_image(
            session, series, device, backend, f"img-leak-{name}"
        )
        patients[name] = patient

    annotations = {}
    for label, image in (("crossed", images["A"]), ("in_scope", images["B"])):
        ann = FormAnnotation(
            FormSchemaID=schema.FormSchemaID,
            PatientID=patients["B"].PatientID,
            ImageInstanceID=image.ImageInstanceID,
            CreatorID=creator.CreatorID,
            FormData={"answer": 1},
        )
        session.add(ann)
        session.flush()
        annotations[label] = ann.FormAnnotationID

    seed = {
        "project_b": patients["B"].ProjectID,
        "patient_b": patients["B"].PatientID,
        "public_a": images["A"].PublicID,
        "public_b": images["B"].PublicID,
        **annotations,
    }
    # Ids read out before the commit and the identity map emptied after it, so
    # the read below issues real SELECTs instead of being answered from memory.
    session.commit()
    session.expunge_all()
    return seed


def _listed_by_id(session, scope, seed):
    from server.dtos.dto_converter import DTOConverter

    service = FormAnnotationService(
        FormAnnotationRepository(session, scope=scope),
        ImageInstanceRepository(session, scope=scope),
        TagRepository(session, scope=scope),
        scope=scope,
    )
    rows = service.list_annotations(
        patient_id=seed["patient_b"],
        study_id=None,
        image_id=None,
        form_schema_id=None,
        sub_task_id=None,
    )
    return {r.FormAnnotationID: DTOConverter.form_annotation_to_get(r) for r in rows}


def test_listing_does_not_disclose_the_public_id_of_an_out_of_reach_image(session):
    """``list_active`` eager-loads ``FormAnnotation.ImageInstance`` and the DTO
    emits its ``PublicID`` as ``image_id`` -- the mirror of the eager-loaded
    annotations collection fixed earlier on this branch, in the other
    direction.

    The annotation itself stays: the caller is entitled to it. Only the
    identifier of the image they cannot reach is withheld. That id 404s on
    ``/images/{id}`` anyway, so this is a bare-identifier leak rather than
    data -- but it still tells a grader in B that a particular image exists
    in a project they hold nothing in.
    """
    seed = _cross_anchored_annotations(session)
    scope = scope_for(seed["project_b"], role=ProjectRole.grader)

    listed = _listed_by_id(session, scope, seed)

    assert set(listed) == {seed["crossed"], seed["in_scope"]}
    assert listed[seed["in_scope"]].image_id == seed["public_b"]
    assert listed[seed["crossed"]].image_id is None


def test_an_administrator_still_sees_both_image_ids(session):
    """The control for the test above: an unbounded scope withholds nothing,
    so the None there means "out of reach" and not "this field went away"."""
    seed = _cross_anchored_annotations(session)

    listed = _listed_by_id(session, admin_scope(), seed)

    assert listed[seed["in_scope"]].image_id == seed["public_b"]
    assert listed[seed["crossed"]].image_id == seed["public_a"]
