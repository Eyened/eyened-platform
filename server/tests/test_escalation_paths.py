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

Their bound, stated exactly. Both scan for a syntactic shape, so what they
prove is "no file outside the list contains this shape", not "no file outside
the list obtains the power". The constructor guard matches the ``is_admin=``
keyword only; ``AccessScope`` is ``kw_only=True`` so a positional third
argument no longer exists, but an alias (``S = AccessScope; S(is_admin=True)``),
``**kwargs`` expansion, ``dataclasses.replace`` and ``object.__setattr__`` are
all invisible to it, as ``setattr(creator, "IsAdmin", True)`` is to the
IsAdmin guard. Files under a ``tests`` path component are not scanned at all.
Nothing here bounds those; review does.
"""
from __future__ import annotations

import ast
import os
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

# Build artifacts that are genuinely recursive: these names mean the same thing
# wherever they appear, so they are pruned at any depth.
#
# `node_modules` is deliberately NOT here, for the reason _EXCLUDED_ROOTS gives
# below for anchoring `client`: it is a name anyone can create inside a Python
# tree, and at any depth it let server/services/node_modules/esc.py hold
# AccessScope(is_admin=True) with all three guards still green. Both real
# node_modules trees live under client/ and docs/, which are root-pruned
# already, so dropping it costs nothing -- measured 208 kept files before and
# after, walk time unchanged.
_EXCLUDED_ANYWHERE = {".git", "__pycache__"}

# Trees that are not this repo's production Python, each naming one specific
# top-level directory. Anchored at the root on purpose: matched at any depth,
# `client` would let a plain HTTP-client package at server/services/client/ opt
# itself out of all three guards, and an escalation could ship green. `docs`
# holds prose and worked examples, not code that runs.
_EXCLUDED_ROOTS = {"client", "docs", "dist", ".svelte-kit", "graphify-out"}

# Virtualenvs are found by their marker file rather than by the name `.venv`,
# because the name is a convention and the guards' blast radius must not depend
# on one. A second environment (`venv/`, `env/`, `.tox/`) would otherwise put
# site-packages under ast.parse, where any third-party `.trusted()` call reports
# as an escalation offender in code nobody in this repo wrote.
_VENV_MARKER = "pyvenv.cfg"


def _python_sources():
    """Every Python file in the repo except an explicit exclusion set. Roots are
    not enumerated: a new top-level tree is exactly where an escalation would be
    invisible, and an allow-list of roots silently grants it that invisibility.

    Tests are excluded because they legitimately build admin scopes all over the
    suite -- including this file, which names the powers it guards.

    The walk prunes in place rather than filtering after the fact, so excluded
    trees are never descended into at all.
    """
    for dirpath, dirnames, filenames in os.walk(_ROOT):
        here = pathlib.Path(dirpath)
        # os.path.isfile, not Path.exists: the marker probe stats a path inside
        # every directory walked, and this tree has unreadable ones (a MySQL
        # dump under database/tmp). Path.exists() re-raises EACCES; isfile
        # returns False, leaving such a directory in the walk exactly as before,
        # where os.walk itself skips it.
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _EXCLUDED_ANYWHERE
            and not (here == _ROOT and d in _EXCLUDED_ROOTS)
            and not os.path.isfile(os.path.join(dirpath, d, _VENV_MARKER))
        ]
        # Tests are pruned by path component, on the path *relative* to the
        # repo: a substring match on the absolute path would also fire for a
        # checkout that happens to live under a directory called `tests`.
        if "tests" in here.relative_to(_ROOT).parts:
            continue
        for name in filenames:
            if name.endswith(".py"):
                yield here / name


def test_only_ensure_admin_writes_is_admin():
    """Creator.IsAdmin has exactly one writer, and it is the bootstrap."""
    # Each guard's exact-set assertion doubles as its own positive control: a
    # walk that collapsed to nothing would fail all three, because every list is
    # non-empty. What that does NOT catch is the scan quietly narrowing back to
    # an enumerated set of roots, so every tree that motivated widening it is
    # asserted here -- all three, because a narrowing that restored two of them
    # would otherwise still pass. A migration is the plausible place to flip
    # this column and it lives outside orm/eyened_orm; notebooks/ is loose
    # scripting; setup.py is a top-level module rather than a package.
    #
    # Checked as "reached", not as an exact set: a *new* top-level tree must be
    # scanned by default rather than have to be listed here, which is the whole
    # reason the walk enumerates no roots.
    expected_reach = {
        "orm/migrations",
        "orm/eyened_orm",
        "orm/setup.py",
        "notebooks",
        "server",
        "dev",
    }
    scanned = {str(p.relative_to(_ROOT)) for p in _python_sources()}
    unreached = {
        tree
        for tree in expected_reach
        if not any(p == tree or p.startswith(tree + "/") for p in scanned)
    }
    assert not unreached

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
