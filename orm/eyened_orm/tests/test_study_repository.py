import datetime

from eyened_orm import Creator, Patient, Project, Study, StudyTagLink, Tag
from eyened_orm.project import ExternalEnum
from eyened_orm.tag import TagType
from eyened_orm.repositories.study_repository import StudyRepository
from eyened_orm.utils.factories import admin_scope


def _make_study(session) -> Study:
    project = Project(ProjectName="P", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier="ID1", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=datetime.date(2020, 1, 1))
    session.add(study)
    session.flush()
    return study


def _make_creator(session) -> Creator:
    creator = Creator(CreatorName="tester", IsHuman=True)
    session.add(creator)
    session.flush()
    return creator


def _make_study_tag(session, creator_id: int) -> Tag:
    tag = Tag(
        TagName="Baseline",
        TagType=TagType.Study,
        TagDescription="",
        CreatorID=creator_id,
    )
    session.add(tag)
    session.flush()
    return tag


def test_get_link_returns_the_link(session):
    """get_link resolves the StudyTagLink by its composite (TagID, StudyID) key."""
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_study_tag(session, creator.CreatorID)
    session.add(
        StudyTagLink(TagID=tag.TagID, StudyID=study.StudyID, CreatorID=creator.CreatorID)
    )
    session.flush()

    result = StudyRepository(session, scope=admin_scope()).get_link(tag.TagID, study.StudyID)
    assert result is not None
    assert result.TagID == tag.TagID
    assert result.StudyID == study.StudyID


def test_get_link_absent_returns_none(session):
    """get_link returns None (never raises) when the pair is not linked."""
    study = _make_study(session)
    assert StudyRepository(session, scope=admin_scope()).get_link(999_999, study.StudyID) is None


def test_get_tag_does_not_load_the_link_collections(session):
    """get_tag reads TagType only, so it must not pull the six selectin
    collections -- 86,190 ImageInstanceTag rows exist on the dev database and
    the worst single tag accounts for 76,647 of them.

    The link below is what makes this non-vacuous: without the noloads the
    collection comes back with one row, so the test fails. Asserting emptiness
    on a tag with no links would pass either way and prove nothing.
    """
    study = _make_study(session)
    creator = _make_creator(session)
    tag = _make_study_tag(session, creator.CreatorID)
    session.add(
        StudyTagLink(
            TagID=tag.TagID, StudyID=study.StudyID, CreatorID=creator.CreatorID
        )
    )
    session.commit()
    # Capture before expunging -- expire_on_commit=True (see sqlite_testdb.py).
    tag_id = tag.TagID
    # Without this the identity map answers session.get() and the options are
    # never applied, so the test would pass with or without the fix.
    session.expunge_all()

    fetched = StudyRepository(session, scope=admin_scope()).get_tag(tag_id)

    assert fetched is not None
    assert fetched.TagType is TagType.Study  # what the caller actually needs
    assert list(fetched.StudyTagLinks) == []
    # ...while the row really is there, so the emptiness is the noload.
    assert session.query(StudyTagLink).count() == 1
