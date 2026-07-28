from eyened_orm import AuditLog, Creator, Tag
from eyened_orm.tag import TagType


def _make_tag(session, creator_id: int) -> Tag:
    tag = Tag(TagName="T1", TagType=TagType.Study, TagDescription="", CreatorID=creator_id)
    session.add(tag)
    session.commit()
    return tag


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
