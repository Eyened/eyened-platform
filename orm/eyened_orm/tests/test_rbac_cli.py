"""The CLI shell: one test, for the one thing the shell adds over the function.

Everything else is tested in test_authz_administration.py, which does not need
a real Database(). The accept path is not retested here: parse_role's happy
path is pinned there, and a CLI-level version of it could only assert that an
error string is *absent* from the output -- which is equally true of any
unrelated failure, so it would pass whether or not the parse ran.
"""
from __future__ import annotations

from click.testing import CliRunner

from eyened_orm.commands.rbac import grant_cmd


def test_an_unknown_role_fails_at_the_boundary_naming_the_valid_ones():
    result = CliRunner().invoke(
        grant_cmd, ["--user", "alice", "--project", "A", "--role", "admin"]
    )
    assert result.exit_code == 2
    for name in ("read_only", "grader", "project_admin"):
        assert name in result.output
