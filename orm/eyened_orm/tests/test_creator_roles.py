import pytest

from eyened_orm import SystemRole, is_system_admin
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
