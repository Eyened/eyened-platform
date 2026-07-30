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
    creator names are enumerated via `Creator.query_column`, reached from the
    one call site at `server/services/search/search_service.py:208-211`
    (already passing a `where=`), which routes through `Base.select`
    (base.py:431) -- and only `Base.query` (base.py:315) carries the automatic
    `~Inactive` filter (base.py:351). A second, independent path is also
    unfiltered on `Creator`: `SearchRepository.active_form_creator_names()`
    (`orm/eyened_orm/repositories/search/repository.py:138-147`) hand-writes
    its own query, filtered on `~FormAnnotation.Inactive` but not
    `Creator.Inactive`, feeding the "Form Creator Name" facet. Filtering both
    is P4's work: amending the existing `where=` on the first site, and adding
    a new `~Creator.Inactive` clause to the second. This pins today's truth so
    P4's change lands as a visible diff rather than a silent one."""
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
    no Inactive clause -- so the five `Creator.by_name` call sites (importer and
    CLI author resolution: task.py:116, study.py:111, segmentation.py:518,
    image_instance.py:790, form_annotation.py:108) keep working after a
    deactivation. If this ever starts returning None, imports break."""
    gone = make_creator(session, "departed")
    gone.Inactive = True
    session.commit()

    assert Creator.by_name(session, "departed") is not None
