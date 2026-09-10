"""Every `TrustedPath` literal names the command it sits in.

New risk, and new with RBAC admin P0. While the audit writer hardcoded
``f"eorm {command}"`` the pairing could not drift; the prefix moved to the CLI
because a production trusted path (``auth:register``) already exists that is not
``eorm``, and that move is what made this guard necessary.

``@click.command("grant-for-task")`` paired with ``TrustedPath("eorm grant")``
is valid Python that writes a plausible, wrong audit row -- provenance that
reads as authoritative and names the wrong command. Nothing else would catch it.

Scope: this matches the literal shape. A name built at runtime
(``TrustedPath(f"eorm {name}")``) is invisible here, which is one reason the
call sites are written as literals.
"""
from __future__ import annotations

import ast
import pathlib

_ORM = pathlib.Path(__file__).resolve().parents[1]
_FILES = (_ORM / "commands" / "rbac.py", _ORM / "cli.py")


def _click_derived_name(func_name: str) -> str:
    """Reproduce Click's bare-decorator name derivation (click/decorators.py).

    Confirmed empirically against the installed click (``orm/setup.py`` pins
    ``click==8.*``; 8.4.2 is what's installed) and against its source: Click
    lowercases the function name, turns underscores into dashes, then -- as
    of click 8.2 -- strips one trailing ``-command``, ``-cmd``, ``-group``, or
    ``-grp`` segment. So ``grant_for_task_cmd`` becomes ``grant-for-task``,
    not ``grant-for-task-cmd``; the suffix must be the trailing segment, so
    ``cmd_foo`` is unaffected and becomes ``cmd-foo``, not ``foo``.
    """
    cmd_name = func_name.lower().replace("_", "-")
    cmd_left, sep, suffix = cmd_name.rpartition("-")
    if sep and suffix in {"command", "cmd", "group", "grp"}:
        cmd_name = cmd_left
    return cmd_name


def _command_name(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """The Click command name this function is registered under, or None.

    Three decorator shapes appear in this repo: ``@click.command("grant")``
    (an explicit name, returned as-is), ``@eorm.command()`` (a bare call with
    no name, so Click derives one -- see ``_click_derived_name``), and a bare
    ``@click.command`` with no parentheses at all (Click permits applying the
    decorator unapplied; the same derivation applies). None of the current
    commands pass the name as a keyword, but Click's signature is
    ``command(name=None, cls=None, **attrs)``, so ``@click.command(name="rm")``
    is legal and would otherwise register under ``rm`` while this function
    kept returning the derived name -- checked below so a future command
    written that way is not silently mismatched.
    """
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            func = decorator.func
            args = decorator.args
            keywords = decorator.keywords
        elif isinstance(decorator, ast.Attribute):
            func = decorator
            args = ()
            keywords = ()
        else:
            continue
        if not (isinstance(func, ast.Attribute) and func.attr == "command"):
            continue
        for arg in args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
        for kw in keywords:
            if (
                kw.arg == "name"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                return kw.value.value
        return _click_derived_name(node.name)
    return None


def _mismatches() -> list[str]:
    bad: list[str] = []
    checked = 0
    for path in _FILES:
        # A renamed or moved module would otherwise make this guard scan
        # nothing and `assert [] == []` pass vacuously.
        assert path.is_file(), f"{path} is missing -- guard would scan nothing"
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = _command_name(node)
            if name is None:
                continue
            for call in ast.walk(node):
                if not (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "TrustedPath"
                    and call.args
                    and isinstance(call.args[0], ast.Constant)
                ):
                    continue
                checked += 1
                written = call.args[0].value
                if written != f"eorm {name}":
                    bad.append(
                        f"{path.name}::{node.name} is `{name}` "
                        f"but writes TrustedPath({written!r})"
                    )
    # Positive control: the walk must actually have found literals to compare.
    # Without this the guard passes on a refactor that stopped writing them.
    #
    # 10 = 9 in rbac.py (one per command, all ten except the read-only
    # check-declarations) + 1 in cli.py (create-user). Legitimately retiring
    # a command means lowering this floor deliberately, not letting a lower
    # count pass silently.
    assert checked >= 10, f"only {checked} TrustedPath literals found in the CLI"
    return bad


def test_click_command_names_match_their_trusted_paths():
    """A command's audit rows name the command the operator actually ran."""
    assert _mismatches() == []
