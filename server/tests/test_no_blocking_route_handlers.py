"""No route handler may be async without awaiting something.

An async def handler that calls synchronous SQLAlchemy runs the query on the
event loop, so the worker serves one request at a time. Declaring it def puts
it in Starlette's threadpool instead. This guard fails the reflex.

What it proves, exactly: no decorated handler is an AsyncFunctionDef whose body
contains no await. It does NOT prove that a synchronous call inside a
legitimately-async handler is wrapped in run_in_threadpool -- that blind spot is
covered by test_route_concurrency.py, not by this file.
"""
from __future__ import annotations

import ast
import pathlib

_ROUTES = pathlib.Path(__file__).resolve().parents[1] / "routes"


def _is_router_decorated(node: ast.AST) -> bool:
    """True for @router.get(...) / @router.post(...) and friends."""
    return any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and isinstance(d.func.value, ast.Name)
        and d.func.value.id == "router"
        for d in node.decorator_list
    )


def _awaits_something(node: ast.AST) -> bool:
    return any(
        isinstance(x, (ast.Await, ast.AsyncFor, ast.AsyncWith)) for x in ast.walk(node)
    )


def _endpoints(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_router_decorated(node):
            yield node


def _offenders_in(source: str, label: str) -> list[str]:
    return [
        f"{label}:{n.lineno} {n.name}"
        for n in _endpoints(ast.parse(source))
        if isinstance(n, ast.AsyncFunctionDef) and not _awaits_something(n)
    ]


def test_no_route_handler_is_async_without_awaiting():
    """Every async endpoint awaits; the rest are def and run in the threadpool."""
    offenders: list[str] = []
    scanned = 0
    for path in sorted(_ROUTES.glob("*.py")):
        source = path.read_text()
        scanned += sum(1 for _ in _endpoints(ast.parse(source)))
        offenders += _offenders_in(source, f"server/routes/{path.name}")

    # Positive control: a walk that silently found nothing would pass an empty
    # offender list. Assert the scan actually reached the endpoints.
    assert scanned >= 70, f"the walk only found {scanned} endpoints; it is not scanning"

    assert not offenders, (
        "these handlers are async but await nothing, so their synchronous work "
        "runs on the event loop and blocks every other request in the worker. "
        "Declare them `def` -- Starlette will run them in a threadpool:\n  "
        + "\n  ".join(offenders)
    )


def test_the_guard_can_fail():
    """Negative control: the guard must reject a handler it is meant to catch.

    A guard that cannot fail is worth nothing, and this one's real assertion is
    an empty-list check -- the shape most likely to pass for the wrong reason.
    """
    bad = (
        "router = object()\n"
        "@router.get('/x')\n"
        "async def handler():\n"
        "    return 1\n"
    )
    assert _offenders_in(bad, "fixture.py") == ["fixture.py:3 handler"]

    good = (
        "router = object()\n"
        "@router.get('/x')\n"
        "def handler():\n"
        "    return 1\n"
    )
    assert _offenders_in(good, "fixture.py") == []
