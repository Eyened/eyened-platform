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


def _command_name(node: ast.FunctionDef) -> str | None:
    """The Click command name this function is registered under, or None.

    Both decorator shapes in this repo are handled: ``@click.command("grant")``
    and ``@eorm.command()``, which Click names from the function itself with
    underscores turned into dashes.
    """
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        func = decorator.func
        if not (isinstance(func, ast.Attribute) and func.attr == "command"):
            continue
        for arg in decorator.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
        return node.name.replace("_", "-")
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
    assert checked >= 10, f"only {checked} TrustedPath literals found in the CLI"
    return bad


def test_click_command_names_match_their_trusted_paths():
    """A command's audit rows name the command the operator actually ran."""
    assert _mismatches() == []
