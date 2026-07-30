import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from eyened_orm import Creator, Project, ProjectMember, ProjectRole
from eyened_orm.utils.factories import make_creator, make_project
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401


def _grant(session, creator, project, role=ProjectRole.grader) -> ProjectMember:
    member = ProjectMember(
        CreatorID=creator.CreatorID, ProjectID=project.ProjectID, Role=role
    )
    session.add(member)
    session.flush()
    return member


def test_role_is_ordered_and_persists_as_its_name(session):
    """SAEnum over an IntEnum stores the member name but round-trips to the
    comparable member, so `role >= grader` checks work off the DB value."""
    creator = make_creator(session, "grader-1")
    project = make_project(session, "P1")
    _grant(session, creator, project, ProjectRole.project_admin)
    session.commit()
    session.expunge_all()

    member = session.scalars(select(ProjectMember)).one()
    assert member.Role is ProjectRole.project_admin
    assert member.Role >= ProjectRole.grader
    assert member.Role > ProjectRole.read_only

    stored = session.connection().exec_driver_sql(
        "select Role from ProjectMember"
    ).scalar()
    assert stored == "project_admin"


def test_one_role_per_creator_per_project(session):
    """The composite PK is what makes AccessScope.roles deterministic: a second
    row for the same pair would make effective_role() last-row-wins."""
    creator = make_creator(session, "dup")
    project = make_project(session, "P1")
    _grant(session, creator, project, ProjectRole.read_only)
    session.commit()

    session.add(
        ProjectMember(
            CreatorID=creator.CreatorID,
            ProjectID=project.ProjectID,
            Role=ProjectRole.project_admin,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_deleting_a_project_cascades_its_grants(session):
    """Grants are meaningless without the project -> CASCADE."""
    creator = make_creator(session, "member")
    project = make_project(session, "doomed")
    _grant(session, creator, project)
    session.commit()

    session.delete(session.get(Project, project.ProjectID))
    session.commit()
    assert session.scalars(select(ProjectMember)).all() == []


def test_deleting_a_creator_with_a_grant_is_refused(session):
    """User deletion is deactivation, so a creator delete must fail loudly rather
    than silently drop an access-review record -> RESTRICT.

    Note *which* error: `IntegrityError` from the database, not SQLAlchemy's
    `AssertionError`. If ProjectMember were reachable from Creator by a loaded
    relationship, the ORM's dependency processor would try to blank the loaded
    child's CreatorID -- a primary-key column -- and raise before emitting any
    SQL. That is precisely the bug P1 spent a phase fixing on Tag's link tables,
    and declaring no relationship is what keeps the constraint reachable here."""
    creator = make_creator(session, "never-deleted")
    project = make_project(session, "P1")
    _grant(session, creator, project)
    session.commit()

    session.delete(session.get(Creator, creator.CreatorID))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
