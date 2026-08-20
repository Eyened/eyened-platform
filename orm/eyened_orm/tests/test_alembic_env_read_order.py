"""env.py's confirmation guard and type comparison must stay wired as designed.

env.py is an Alembic script, not an importable module, so this parses it.

Scope, stated so the guard is not over-trusted: it checks the lexical position
of module-level statements, not runtime order. Calls nested in a function or
class body are deliberately excluded rather than trusted -- env.py runs top to
bottom at import, so a read reached through a helper has no meaningful position
and is rejected outright. Arbitrarily dynamic constructions are not modelled;
review is the backstop for the general case.
"""

from __future__ import annotations

import ast
import pathlib

ENV_PY = pathlib.Path(__file__).resolve().parents[2] / "migrations" / "alembic" / "env.py"

_FLAG = "EYENED_ALEMBIC_ASSUME_YES"
_ACCEPTED_READS = frozenset({f"os.environ.get('{_FLAG}')", f"os.getenv('{_FLAG}')"})


def _module_ast() -> ast.Module:
    # A moved or renamed env.py would otherwise make every assertion vacuous.
    assert ENV_PY.is_file(), f"{ENV_PY} does not exist -- guard would check nothing"
    return ast.parse(ENV_PY.read_text(), filename=str(ENV_PY))


def _module_level_calls(tree: ast.Module, name: str) -> list[ast.Call]:
    calls = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        calls.extend(
            n
            for n in ast.walk(stmt)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == name
        )
    return calls


def _configure_call(tree: ast.Module, function_name: str) -> ast.Call:
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef) and stmt.name == function_name:
            for node in ast.walk(stmt):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "configure"
                ):
                    return node
    raise AssertionError(f"{function_name}() has no context.configure(...) call")


def _keyword_is_true(call: ast.Call, name: str) -> bool:
    return any(
        kw.arg == name and isinstance(kw.value, ast.Constant) and kw.value.value is True
        for kw in call.keywords
    )


def test_assume_yes_is_read_from_the_environment_above_load_env_file():
    """load_env_file is load_dotenv(override=True), so a later read is bypassable."""
    tree = _module_ast()
    flag_calls = _module_level_calls(tree, "env_flag_enabled")
    load_calls = _module_level_calls(tree, "load_env_file")

    assert load_calls, "env.py must call load_env_file() at module level"
    assert any(
        call.args and ast.unparse(call.args[0]) in _ACCEPTED_READS
        for call in flag_calls
    ), (
        f"env.py must read {_FLAG} straight from the process environment at module "
        f"level, written as one of {sorted(_ACCEPTED_READS)} -- not from settings, "
        "not from a loaded file, not inside a helper"
    )

    last_flag = max(call.lineno for call in flag_calls)
    first_load = min(call.lineno for call in load_calls)
    assert last_flag < first_load, (
        f"an env_flag_enabled() call at line {last_flag} sits below load_env_file() "
        f"at line {first_load}; load_env_file is load_dotenv(override=True), so any "
        ".env file could switch the confirmation guard off"
    )


def test_online_migrations_compare_column_types():
    """Removing compare_type has no failure signal: the gate would stay green."""
    tree = _module_ast()

    assert _keyword_is_true(_configure_call(tree, "run_migrations_online"), "compare_type"), (
        "run_migrations_online must configure compare_type=True, or alembic check "
        "silently stops detecting column type drift"
    )
    assert not _keyword_is_true(_configure_call(tree, "run_migrations_offline"), "compare_type"), (
        "compare_type in run_migrations_offline is inert churn -- autogenerate and "
        "check are online-only"
    )


def test_the_confirmation_prompt_still_exists():
    """An opt-out is only meaningful while there is something to opt out of."""
    tree = _module_ast()

    assert _module_level_calls(tree, "input"), (
        "env.py no longer prompts before altering a database, so the assume-yes "
        "flag now guards nothing"
    )


def test_online_configure_passes_render_item():
    """A correct renderer that nothing calls is worth nothing."""
    call = _configure_call(_module_ast(), "run_migrations_online")
    assert any(kw.arg == "render_item" for kw in call.keywords), (
        "run_migrations_online()'s context.configure(...) does not pass render_item; "
        "OptionalEnum columns would autogenerate as code that cannot run"
    )
