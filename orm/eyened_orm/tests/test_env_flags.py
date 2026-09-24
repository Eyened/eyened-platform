import pytest

from eyened_orm.utils.env import env_flag_enabled


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        (" yes ", True),
        (None, False),
        ("", False),
        ("false", False),
        ("0", False),
        ("y", False),
    ],
)
def test_env_flag_enabled_accepts_only_the_allowlist(value, expected):
    """`false` must not enable the flag — truthiness is the wrong failure direction."""
    assert env_flag_enabled(value) is expected
