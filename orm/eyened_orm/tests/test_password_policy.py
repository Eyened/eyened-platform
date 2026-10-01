"""check_new_password: NIST SP 800-63B-4 length bounds and the context blocklist."""
from __future__ import annotations

import pytest

from eyened_orm.utils.db_users import WeakPasswordError, check_new_password


@pytest.mark.parametrize(
    "password,username",
    [
        ("a" * 15, "alice"),
        ("a" * 128, "alice"),
        ("bob's own long passphrase", "bob"),
    ],
    ids=["15", "128", "3-char-username-unchecked"],
)
def test_an_acceptable_password_passes(password, username):
    """No exception is the pass."""
    check_new_password(password, username=username)


@pytest.mark.parametrize(
    "password,username,message",
    [
        ("a" * 14, "alice", "at least 15"),
        ("a" * 129, "alice", "at most 128"),
        ("my own ALICE passphrase", "alice", "the username"),
        ("root-and-a-long-tail", "root", "the username"),
        ("my EyEnEd passphrase here", "bob", "'eyened'"),
    ],
    ids=["14", "129", "username-any-case", "4-char-username", "eyened-any-case"],
)
def test_a_weak_password_names_the_rule(password, username, message):
    """The message is what the 400 and the CLI print."""
    with pytest.raises(WeakPasswordError, match=message):
        check_new_password(password, username=username)
