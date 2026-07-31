from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from eyened_orm import Creator, CreatorTagLink, Tag
from eyened_orm.tag import (
    AnnotationTagLink,
    FormAnnotationTagLink,
    ImageInstanceTagLink,
    SegmentationTagLink,
    StudyTagLink,
    TagType,
)
from eyened_orm.repositories.tag_repository import TagRepository
from eyened_orm.utils.factories import make_patient, make_project, make_study


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


def test_delete_refuses_a_tag_that_is_still_applied(session):
    """The database refuses to delete a tag an annotation row still references.

    RESTRICT on the five annotation-link TagID FKs means the delete surfaces as
    an IntegrityError rather than cascading the links away (spec §3.2.1).
    """
    creator = _make_creator(session)
    project = make_project(session, "P1")
    patient = make_patient(session, project, "pat-1")
    study = make_study(session, patient, date(2020, 1, 1))
    tag = _make_tag(session, creator.CreatorID, "Applied")
    session.add(
        StudyTagLink(
            TagID=tag.TagID, StudyID=study.StudyID, CreatorID=creator.CreatorID
        )
    )
    session.commit()
    tag_id = tag.TagID
    # Load-bearing, not tidiness: seeding leaves the tag in the identity map, so
    # session.get() would return it with the six collections never loaded --
    # which is the one state where today's code deletes happily and wipes the
    # link. Expunging makes get_by_id emit real SQL, exactly as a request does,
    # so this test exercises the noload as well as the FK. See Step 2.
    session.expunge_all()
    repository = TagRepository(session)

    with pytest.raises(IntegrityError):
        repository.delete(repository.get_by_id(tag_id))

    session.rollback()
    # The refusal destroyed nothing -- both rows are still committed.
    assert session.get(Tag, tag_id) is not None
    assert session.query(StudyTagLink).count() == 1


def test_delete_allows_a_tag_nobody_has_applied(session):
    """An unapplied tag stays freely deletable -- v0.2's user-writable namespace."""
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID, "Unapplied")
    repository = TagRepository(session)

    repository.delete(repository.get_by_id(tag.TagID))

    assert repository.get_by_id(tag.TagID) is None


def test_delete_allows_a_starred_tag_and_drops_the_star(session):
    """A star never blocks a delete; CreatorTag still cascades.

    Also the regression test for a live 500: CreatorTag.TagID is a primary-key
    column, so while get_by_id loaded the star collection the ORM raised
    AssertionError ("tried to blank-out primary key column") before emitting SQL.
    The commit/expunge is what puts the test on that path -- without it the star
    collection is never loaded and the test passes even against today's code.
    """
    creator = _make_creator(session)
    tag = _make_tag(session, creator.CreatorID, "Starred")
    session.add(CreatorTagLink(TagID=tag.TagID, CreatorID=creator.CreatorID))
    session.commit()
    tag_id = tag.TagID
    session.expunge_all()
    repository = TagRepository(session)

    repository.delete(repository.get_by_id(tag_id))

    assert repository.get_by_id(tag_id) is None
    assert session.query(CreatorTagLink).count() == 0


def test_get_by_id_does_not_load_the_link_collections(session):
    """get_by_id leaves the link collections unloaded even when links exist.

    Pins the mechanism the delete path depends on: Tag maps them lazy="selectin",
    so a plain session.get() loads all six and the ORM then pre-empts the FK
    constraint. If this regresses, the refusal above becomes a 500 instead.

    The links below are what make this non-vacuous: drop the noload from
    get_by_id and both collections come back with one row each, so the test
    fails. Asserting empty collections on a tag with no links would pass either
    way and prove nothing.
    """
    creator = _make_creator(session)
    project = make_project(session, "P1")
    patient = make_patient(session, project, "pat-1")
    study = make_study(session, patient, date(2020, 1, 1))
    tag = _make_tag(session, creator.CreatorID, "Fresh")
    session.add(
        StudyTagLink(
            TagID=tag.TagID, StudyID=study.StudyID, CreatorID=creator.CreatorID
        )
    )
    session.add(CreatorTagLink(TagID=tag.TagID, CreatorID=creator.CreatorID))
    session.commit()
    tag_id = tag.TagID
    # Otherwise session.get() returns the identity-map instance and the
    # options are never applied.
    session.expunge_all()

    fetched = TagRepository(session).get_by_id(tag_id)

    assert fetched is not None
    assert list(fetched.StudyTagLinks) == []
    assert list(fetched.CreatorTagLinks) == []
    # ...while the rows really are there, so the emptiness is the noload.
    assert session.query(StudyTagLink).count() == 1
    assert session.query(CreatorTagLink).count() == 1


def test_only_the_annotation_link_fks_restrict_tag_deletes():
    """All five annotation-link TagID FKs RESTRICT; CreatorTag alone cascades.

    The behavioural tests above exercise StudyTag only, so on their own they
    would stay green if one of the other four edits were missed -- and the five
    edits are textually identical to a sixth that must NOT change. Assert the
    whole rule as a table instead of trusting one table to generalise.
    """
    rules = {}
    for link in (
        CreatorTagLink,
        StudyTagLink,
        ImageInstanceTagLink,
        AnnotationTagLink,
        SegmentationTagLink,
        FormAnnotationTagLink,
    ):
        (tag_fk,) = [
            fk
            for fk in link.__table__.foreign_keys
            if fk.column.table.name == "Tag"
        ]
        rules[link.__tablename__] = tag_fk.ondelete

    assert rules == {
        "StudyTag": "RESTRICT",
        "ImageInstanceTag": "RESTRICT",
        "AnnotationTag": "RESTRICT",
        "SegmentationTag": "RESTRICT",
        "FormAnnotationTag": "RESTRICT",
        "CreatorTag": "CASCADE",
    }


def test_every_tag_link_collection_is_noloaded():
    """TAG_LINK_COLLECTIONS covers every relationship the delete path must not load.

    A Tag relationship whose *target's* primary key contains TagID is a link
    collection: loading it makes the ORM's dependency processor try to blank a
    primary-key column when the tag is deleted, raising AssertionError before
    the foreign key can speak (spec §3.2.1). Tag.Creator is correctly excluded
    -- its PK is CreatorID.

    Deriving the requirement from the mapper rather than only restating six
    names means a seventh link table turns this test red the day it is added,
    rather than slipping through uncovered. It also closes a gap no behavioural
    test here could: each noload only prevents the assertion for *its own*
    collection, and only StudyTag and CreatorTag have a test that applies a
    link, so four of the six could be deleted with the suite green.
    """
    from sqlalchemy import inspect as sa_inspect

    from eyened_orm.tag import TAG_LINK_COLLECTIONS

    required = {
        relationship.key
        for relationship in sa_inspect(Tag).relationships
        if any(column.name == "TagID" for column in relationship.mapper.primary_key)
    }
    assert required == {
        "CreatorTagLinks",
        "StudyTagLinks",
        "ImageInstanceTagLinks",
        "AnnotationTagLinks",
        "SegmentationTagLinks",
        "FormAnnotationTagLinks",
    }, (
        "Tag's set of link collections changed -- update BOTH "
        "TAG_LINK_COLLECTIONS in eyened_orm/tag.py AND this literal"
    )

    assert {attribute.key for attribute in TAG_LINK_COLLECTIONS} == required
