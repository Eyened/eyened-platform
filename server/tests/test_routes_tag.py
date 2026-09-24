from datetime import date

from eyened_orm import AuditLog, Creator, Tag
from eyened_orm.tag import StudyTagLink, TagType
from eyened_orm.utils.factories import make_patient, make_project, make_study


def _make_tag(session, creator_id: int) -> Tag:
    tag = Tag(TagName="T1", TagType=TagType.Study, TagDescription="", CreatorID=creator_id)
    session.add(tag)
    session.commit()
    return tag


def test_post_tag_audits_the_enum_value_not_its_repr(client, session):
    """POST /tags records tag_type as "Study", not "TagType.Study".

    The INSERT payload passes the raw enum and lets AuditService normalize it,
    exactly as the UPDATE and DELETE payloads do. A str() at the call site
    would bypass that normalization and store the member's repr, leaving the
    same field spelled two different ways across an entity's audit history.
    """
    # The client fixture's CurrentUser is creator_id=1; the tag's CreatorID FK
    # needs that row to exist.
    session.add(Creator(CreatorName="alice", IsHuman=True))
    session.commit()

    response = client.post(
        "/tags",
        json={"name": "T2", "tag_type": "Study", "description": "d"},
    )

    assert response.status_code == 200, response.text
    row = session.query(AuditLog).filter_by(Entity="Tag", Action="INSERT").one()
    assert row.Changes["tag_type"] == "Study"


def test_patch_tag_tag_type_persists_and_audits(client, session):
    """PATCH /tags/{id} changing tag_type succeeds (200) and persists the new
    TagType, with one AuditLog row recording the enum values as strings.

    This is the HTTP-level regression test for the enum-in-changes 500: the
    full DI stack (route -> TagService -> AuditService.record()) is what
    originally hit `TypeError: Object of type TagType is not JSON
    serializable` on flush, because the value AuditService.snapshot() captured
    is the raw TagType enum loaded from the DB, not a string. Discriminator:
    reverting the json-safe normalization in AuditService.record() makes this
    fail with a 500.
    """
    creator = Creator(CreatorName="alice", IsHuman=True)
    session.add(creator)
    session.commit()
    tag = _make_tag(session, creator.CreatorID)

    response = client.patch(f"/tags/{tag.TagID}", json={"tag_type": "ImageInstance"})

    assert response.status_code == 200, response.text
    updated = session.get(Tag, tag.TagID)
    assert updated.TagType == TagType.ImageInstance

    audit_rows = (
        session.query(AuditLog).filter_by(Entity="Tag", EntityID=str(tag.TagID)).all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].Changes == {
        "TagType": {"old": "Study", "new": "ImageInstance"}
    }


def test_delete_tag_still_applied_returns_409(client, session):
    """DELETE /tags/{id} on an applied tag returns 409 with a structured code.

    The full stack test: the FK raises IntegrityError, TagService maps it to
    ConflictError, and the single ServiceError handler assigns the status --
    no per-route wiring (spec §3.3.1).
    """
    creator = Creator(CreatorName="alice", IsHuman=True)
    session.add(creator)
    session.commit()
    tag = _make_tag(session, creator.CreatorID)
    project = make_project(session, "P1")
    patient = make_patient(session, project, "pat-1")
    study = make_study(session, patient, date(2020, 1, 1))
    session.add(
        StudyTagLink(
            TagID=tag.TagID, StudyID=study.StudyID, CreatorID=creator.CreatorID
        )
    )
    session.commit()
    tag_id = tag.TagID
    # The client fixture binds the request to *this* Session
    # (server/tests/conftest.py), so without expunging, the handler's
    # session.get() is an identity-map hit with the link collections unloaded --
    # and this test would then pass with or without Task 1's noload, i.e. prove
    # only half of what it claims. Expunging gives the request the fresh-Session
    # semantics it has in production.
    session.expunge_all()

    response = client.delete(f"/tags/{tag_id}")

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "TAG_IN_USE"
    # The tag and its link survived the refused delete.
    assert session.get(Tag, tag_id) is not None
    assert session.query(StudyTagLink).count() == 1


def test_delete_unapplied_tag_returns_204(client, session):
    """DELETE /tags/{id} still succeeds for a tag nobody has applied."""
    creator = Creator(CreatorName="alice", IsHuman=True)
    session.add(creator)
    session.commit()
    tag = _make_tag(session, creator.CreatorID)

    response = client.delete(f"/tags/{tag.TagID}")

    assert response.status_code == 204, response.text
    assert session.get(Tag, tag.TagID) is None
