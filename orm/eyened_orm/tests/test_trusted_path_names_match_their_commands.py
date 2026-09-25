"""Every `TrustedPath` literal names the command it sits in.

New risk, and new with RBAC admin P0. While the audit writer hardcoded
``f"eorm {command}"`` the pairing could not drift; the prefix moved to the CLI
because a production trusted path (``auth:register``) already exists that is not
``eorm``, and that move is what made this guard necessary.

``@click.command("grant-for-task")`` paired with ``TrustedPath("eorm grant")``
is valid Python that writes a plausible, wrong audit row -- provenance that
reads as authoritative and names the wrong command. Nothing else would catch it.

The two halves of the pair are read from the two places that own them: the
command name off the ``click.Command`` object the decorator produced (Click
computed it, so nothing here has to reproduce Click -- see ``_registered_names``),
and the ``TrustedPath`` literal off the same function's AST.

Scope: this matches the literal shape. A name built at runtime
(``TrustedPath(f"eorm {name}")``) is invisible here, which is one reason the
call sites are written as literals. Likewise a command built inside a function
rather than at module scope: it is not in the module's namespace, so the pairing
below never sees it.
"""
from __future__ import annotations

import ast
import pathlib
import types

import click

from eyened_orm import cli as cli_module
from eyened_orm.commands import rbac as rbac_module

_ORM = pathlib.Path(__file__).resolve().parents[1]
# Each file paired with the module it is the source of: the AST supplies the
# TrustedPath literals, the imported module supplies the names Click registered.
_FILES = (
    (_ORM / "commands" / "rbac.py", rbac_module),
    (_ORM / "cli.py", cli_module),
)


def _registered_names(module: types.ModuleType) -> dict[str, str]:
    """Map ``function name -> the command name Click registered it under``.

    Ask Click rather than reproduce it. Every decorated module-level object
    *is* a ``click.Command`` -- ``click.Group`` too, which subclasses it and is
    how the ``eorm`` group in ``cli.py`` arrives here -- carrying a ``.name``
    Click itself computed and a ``.callback`` that is the undecorated function,
    whose ``__name__`` is what the AST walk below sees.

    That closes every decorator shape at once: a positional name, ``name=``,
    ``@eorm.command()``, and a bare ``@click.command`` with no parentheses --
    including any shape a future Click adds. The derivation this replaces
    (lowercase, ``_`` to ``-``, then strip one trailing
    ``-command``/``-cmd``/``-group``/``-grp``) is Click 8.2-and-later behaviour
    while ``orm/setup.py`` pins only ``click==8.*``, so a reimplementation could
    disagree with what Click actually registers under a version the pin already
    permits -- and this guard would then go quietly wrong instead of failing.
    """
    return {
        obj.callback.__name__: obj.name
        for obj in vars(module).values()
        if isinstance(obj, click.Command) and obj.callback is not None
    }


def _mismatches() -> list[str]:
    bad: list[str] = []
    checked = 0
    for path, module in _FILES:
        # A renamed or moved module would otherwise make this guard scan
        # nothing and `assert [] == []` pass vacuously.
        assert path.is_file(), f"{path} is missing -- guard would scan nothing"
        registered = _registered_names(module)
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = registered.get(node.name)
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
