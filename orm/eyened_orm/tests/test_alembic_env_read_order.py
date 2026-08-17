"""The assume-yes flag must be read from os.environ, above load_env_file.

env.py is an Alembic script, not an importable module, so this parses it.
"""

from __future__ import annotations

import ast
import pathlib

ENV_PY = pathlib.Path(__file__).resolve().parents[2] / "migrations" / "alembic" / "env.py"


def _calls(tree: ast.Module, name: str) -> list[ast.Call]:
    return [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name
    ]


def test_assume_yes_is_read_from_the_environment_above_load_env_file():
    """load_env_file is load_dotenv(override=True), so a later read is bypassable."""
    assert ENV_PY.is_file(), f"{ENV_PY} does not exist -- guard would check nothing"
    tree = ast.parse(ENV_PY.read_text(), filename=str(ENV_PY))

    flag_calls = _calls(tree, "env_flag_enabled")
    load_calls = _calls(tree, "load_env_file")
    assert flag_calls and load_calls, "env.py must call env_flag_enabled and load_env_file"

    assert any(
        call.args and ast.unparse(call.args[0]) == "os.environ.get('EYENED_ALEMBIC_ASSUME_YES')"
        for call in flag_calls
    ), "read the flag straight from os.environ, not from settings or a loaded file"

    flag_line = min(c.lineno for c in flag_calls)
    load_line = min(c.lineno for c in load_calls)
    assert flag_line < load_line, (
        f"env_flag_enabled() at line {flag_line} sits below load_env_file() at line "
        f"{load_line}; any .env file could then switch the confirmation guard off"
    )
