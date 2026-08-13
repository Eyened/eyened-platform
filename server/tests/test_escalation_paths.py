"""Two unbounded powers, each pinned to an explicit allow-list.

Every write path to Creator.IsAdmin is an escalation path: making the column
load-bearing turns any endpoint that can set it into a way to become an
administrator. It is clean by construction today -- create_user takes no such
argument, so /auth/register and OIDC auto-provision both land at the False
default -- but that list is only exhaustive if it stays that way, and it is
what keeps the deferred registration modes from opening a hole when they land.

The second power, an unbounded AccessScope, has two doors: AccessScope.trusted()
and the constructor with is_admin=True. Both are guarded, because guarding only
the first would leave a green suite and an open door.

These guards are allow-lists over source, so they are exact-set assertions on
purpose: a file that stops needing the power must leave the list, and the test
failing is how you find out.
"""
from __future__ import annotations

import ast
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Files permitted to assign Creator.IsAdmin. The walk below sees attribute
# assignment and the keyword form only: setattr(creator, "IsAdmin", True) and
# Creator(**data) both slip past it, so this bounds the obvious writes rather
# than proving there are no others.
_ISADMIN_WRITERS = {
    "orm/eyened_orm/authz/bootstrap.py",  # ensure_admin, the only writer
}

# Files permitted to call AccessScope.trusted(). Every entry is a path v0.3
# places outside enforcement.
_TRUSTED_CALLERS = {
    "server/routes/auth.py",  # pre-authentication token refresh / OIDC
}

# Files permitted to construct an AccessScope whose is_admin is anything but a
# literal False -- the other way to an unbounded scope, which a .trusted() scan
# does not see. Passing is_admin=False is unrestricted and not listed here.
_ADMIN_SCOPE_BUILDERS = {
    "server/services/access_scope.py",     # get_access_scope, from the DB row
    "orm/eyened_orm/utils/factories.py",   # admin_scope/scope_for, test support
}

# Directories whose Python is not this repo's production source: third-party
# trees, build output, and the client. `docs` holds prose and worked examples,
# not code that runs.
_EXCLUDED = {".git", "node_modules", ".venv", "__pycache__", "client", "dist",
             ".svelte-kit", "graphify-out", "docs"}


def _python_sources():
    """Every Python file in the repo except an explicit exclusion set. Roots are
    not enumerated: a new top-level tree is exactly where an escalation would be
    invisible, and an allow-list of roots silently grants it that invisibility.

    Tests are excluded because they legitimately build admin scopes all over the
    suite -- including this file, which names the powers it guards.
    """
    for path in _ROOT.rglob("*.py"):
        parts = path.relative_to(_ROOT).parts
        if any(p in _EXCLUDED for p in parts) or "/tests/" in path.as_posix():
            continue
        yield path


def test_only_ensure_admin_writes_is_admin():
    """Creator.IsAdmin has exactly one writer, and it is the bootstrap."""
    # Each guard's exact-set assertion doubles as its own positive control: a
    # walk that collapsed to nothing would fail all three, because every list is
    # non-empty. What that does NOT catch is the scan quietly narrowing back to
    # an enumerated set of roots, so the one tree that motivated widening it is
    # asserted here -- a migration is the plausible place to flip this column,
    # and it lives outside orm/eyened_orm.
    scanned = {str(p.relative_to(_ROOT)) for p in _python_sources()}
    assert any(p.startswith("orm/migrations/") for p in scanned)

    offenders = set()
    for path in _python_sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr == "IsAdmin":
                    offenders.add(str(path.relative_to(_ROOT)))
            # keyword form: Creator(..., IsAdmin=True)
            if isinstance(node, ast.Call) and any(
                kw.arg == "IsAdmin" for kw in node.keywords
            ):
                offenders.add(str(path.relative_to(_ROOT)))
    assert offenders == _ISADMIN_WRITERS


def test_only_the_allow_listed_files_call_access_scope_trusted():
    """The unbounded-scope escape hatch is reachable from one file only.

    ``audit_trusted`` in authz/administration.py and commands/rbac.py is a bare
    Name call, not an attribute, so it does not match here. Do not "fix" that
    with a substring search -- it would flag every one of those call sites.
    """
    offenders = set()
    for path in _python_sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "trusted"
            ):
                offenders.add(str(path.relative_to(_ROOT)))
    assert offenders == _TRUSTED_CALLERS


def test_only_the_allow_listed_files_decide_a_scopes_admin_flag():
    """AccessScope(is_admin=...) is the second door to an unbounded scope.

    get_access_scope is on the list because deriving the flag from the Creator
    row is the one legitimate way in; the point is that nothing else may.
    """
    offenders = set()
    for path in _python_sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "AccessScope"
            ):
                continue
            for kw in node.keywords:
                if kw.arg == "is_admin" and not (
                    isinstance(kw.value, ast.Constant) and kw.value.value is False
                ):
                    offenders.add(str(path.relative_to(_ROOT)))
    assert offenders == _ADMIN_SCOPE_BUILDERS


def test_create_user_cannot_make_an_administrator():
    """/auth/register and OIDC auto-provision both go through it."""
    import inspect

    from eyened_orm.utils.db_users import create_user

    assert "is_admin" not in inspect.signature(create_user).parameters
