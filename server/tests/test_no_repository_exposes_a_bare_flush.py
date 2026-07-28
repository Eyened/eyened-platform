"""Repositories name the write-back for intent, not mechanism.

Every repository write-back is ``save()``/``save_link()``. A public ``flush()``
would put a persistence mechanism back in the service layer's vocabulary, which
is exactly what the rename removed.

Scope, stated so the guard is not over-trusted: this catches the *name*
``flush``, not the pattern. A future ``persist()`` or ``sync()`` with a bare
``self._session.flush()`` body would pass. A body-based check is deliberately
not used -- the ``save*`` methods this guard protects are themselves exactly
that body, so it would flag them. Review is the backstop for the general case.
"""

from __future__ import annotations

import ast
import pathlib

_REPOSITORIES = (
    pathlib.Path(__file__).resolve().parents[2]
    / "orm"
    / "eyened_orm"
    / "repositories"
)


def _public_flush_methods(root: pathlib.Path) -> list[str]:
    # A moved/renamed source tree would otherwise make rglob() silently yield
    # nothing and `assert [] == []` would pass vacuously -- fail loudly instead.
    assert root.is_dir(), f"{root} is not a directory -- guard would scan nothing"
    offenders: list[str] = []
    scanned = 0
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        scanned += 1
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if (
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name == "flush"
                ):
                    offenders.append(
                        f"{path.relative_to(root).as_posix()}::{node.name}.flush"
                    )
    assert scanned, f"{root} contained no .py files -- guard would scan nothing"
    return sorted(offenders)


def test_no_repository_exposes_a_bare_flush():
    """No repository class defines a public flush(); write-backs are save*()."""
    assert _public_flush_methods(_REPOSITORIES) == []
