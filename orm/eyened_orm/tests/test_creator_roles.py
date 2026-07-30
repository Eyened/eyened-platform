import pytest

from eyened_orm import Creator, SystemRole, is_system_admin
from eyened_orm.utils.factories import make_creator
from eyened_orm.utils.sqlite_testdb import session  # noqa: F401


@pytest.mark.parametrize(
    "role, expected",
    [
        (None, False),  # the state of all 74 production rows pre-cutover
        (SystemRole.user, False),
        (SystemRole.system_admin, True),
    ],
)
def test_is_system_admin_only_for_the_admin_role(session, role, expected):
    """NULL and `user` are both non-admins; only system_admin is a data superuser.
    The NULL case is the one that matters most -- it is every existing row."""
    creator = make_creator(session, "subject")
    creator.Role = role
    assert is_system_admin(creator) is expected


def test_deactivation_does_not_yet_hide_a_creator_from_the_search_facet(session):
    """Characterization: adding the column does NOT make deactivated users
    disappear from the creator search facet. The instance-signature facet's
    creator names are enumerated via `Creator.query_column`, reached from
    `server/services/search/search_service.py:208-212` (the `where=` P4 must
    amend is the one at line 210) through an intermediate hop --
    `SearchRepository.column_values()`
    (`orm/eyened_orm/repositories/search/repository.py:206-212`), a thin
    wrapper -- which routes through `Base.select` (base.py:431). Two helpers,
    not one, carry the automatic `~Inactive` filter: `Base.query` (base.py:315,
    filter at base.py:351) and `Base.where` (base.py:607, filter at
    base.py:621); neither is in this call chain, and no `Creator.where(` call
    exists anywhere today. A second, independent path is also unfiltered on
    `Creator`: `SearchRepository.active_form_creator_names()`
    (`orm/eyened_orm/repositories/search/repository.py:138-147`) hand-writes
    its own query, filtered on `~FormAnnotation.Inactive` but not
    `Creator.Inactive`, feeding the "Form Creator Name" facet. Filtering both
    is P4's work: amending the existing `where=` on the first site (line 210),
    and adding a new `~Creator.Inactive` clause to the second. This pins
    today's truth so P4's change lands as a visible diff rather than a silent
    one."""
    make_creator(session, "present")
    gone = make_creator(session, "departed")
    gone.Inactive = True
    session.commit()

    names = Creator.query_column(session, Creator.CreatorName)
    assert sorted(names) == ["departed", "present"]


def test_base_query_honours_the_new_column(session):
    """The one helper that does respect it, waivable for admin/audit reads. No
    caller routes Creator through it today, so this documents the semantics the
    column just acquired rather than a behaviour change."""
    make_creator(session, "present")
    gone = make_creator(session, "departed")
    gone.Inactive = True
    session.commit()

    assert [c.CreatorName for c in Creator.query(session)] == ["present"]
    assert sorted(
        c.CreatorName for c in Creator.query(session, include_inactive=True)
    ) == ["departed", "present"]


def test_by_name_still_resolves_a_deactivated_creator(session):
    """A deactivated grader's authored work stays attributed and visible.
    `by_name` builds via _build_where_stmt, which carries
    no Inactive clause -- so the six `Creator.by_name` call sites (importer and
    CLI author resolution: task.py:116, study.py:111, segmentation.py:518,
    image_instance.py:790, form_annotation.py:108, form_annotation.py:177)
    keep working after a deactivation. A seventh site reaches `Creator` by the
    same unfiltered `_build_where_stmt` path via `Creator.by_column`
    (`orm/eyened_orm/importer/segmentation_import.py:63`). If this ever starts
    returning None, imports break."""
    gone = make_creator(session, "departed")
    gone.Inactive = True
    session.commit()

    assert Creator.by_name(session, "departed") is not None
