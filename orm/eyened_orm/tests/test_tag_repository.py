from eyened_orm import Creator, Tag
from eyened_orm.tag import TagType
from eyened_orm.repositories.tag_repository import TagRepository


def _make_creator(session, name: str = "tester") -> Creator:
    creator = Creator(CreatorName=name, IsHuman=True)
    session.add(creator)
    session.flush()
    return creator


def _make_tag(
    session, creator_id: int, name: str, tag_type: TagType = TagType.Study
) -> Tag:
    tag = Tag(
        TagName=name, TagType=tag_type, TagDescription="", CreatorID=creator_id
    )
    session.add(tag)
    session.flush()
    return tag


def test_list_all_returns_all_tags_with_creator(session):
    """list_all returns every tag with its Creator eager-loaded (no lazy fan-out)."""
    creator = _make_creator(session)
    _make_tag(session, creator.CreatorID, "Beta")
    _make_tag(session, creator.CreatorID, "Alpha", TagType.ImageInstance)

    tags = TagRepository(session).list_all()

    assert sorted(t.TagName for t in tags) == ["Alpha", "Beta"]
    # Creator was selectinload-ed, so reading it needs no extra lazy query.
    assert tags[0].Creator.CreatorName == "tester"
