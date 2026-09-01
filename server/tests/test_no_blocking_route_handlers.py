"""No route handler may be async without awaiting something.

An async def handler that calls synchronous SQLAlchemy runs the query on the
event loop, so the worker serves one request at a time. Declaring it def puts
it in Starlette's threadpool instead. This guard fails the reflex.

What it proves, exactly: no decorated handler is an AsyncFunctionDef whose body
contains no await, other than those declared in `_MUST_STAY_ASYNC` below.

That dict is also a pin in the other direction: every handler in it must still
exist and must still be `async def`. Exempting alone would permit the opposite
mistake -- converting a loop-bound handler to `def` -- which for three of the
five nothing else would catch, because they await a request body and so satisfy
the await guard whichever way they are declared.

Blind spot: it does NOT prove that a synchronous call inside a
legitimately-async handler is wrapped in run_in_threadpool. Nothing covers that
-- test_route_concurrency.py drives `/task` and `/features`, both plain `def`,
so it exercises none of the async handlers and says nothing about this case.

Scope: `server/routes/**/*.py`, and only decorators written on a name literally
called `router`. `server/main.py`'s `@app.get("/health")` is an
async handler that awaits nothing and is deliberately outside that reach -- its
body is a literal dict return with no I/O, so it never blocks the loop.
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
    """True if the handler's OWN body awaits something.

    ast.walk descends into nested function bodies, so a nested `async def`
    helper's await would otherwise clear a handler whose own body blocks.
    A nested function's awaits belong to that function, not to this one.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(child, (ast.Await, ast.AsyncFor, ast.AsyncWith)):
            return True
        if _awaits_something(child):
            return True
    return False


def _endpoints(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_router_decorated(node):
            yield node


# Handlers that must stay `async def`, and why. Keyed on the same path the
# offender list prints, not on the bare filename, so a routes file added under
# another root cannot inherit an entry by basename collision.
#
# All five touch the segmentation zarr store, which has no write lock: the event
# loop is the only thing serializing access to it within a worker. The two
# readers await nothing, so they need exempting from the await guard. The three
# writers await a request body and would satisfy that guard either way -- they
# are listed because the pin below is the only thing keeping them off the
# threadpool. What would remove all five: a lock in the storage layer, which is
# separate work.
_MUST_STAY_ASYNC: dict[tuple[str, str], str] = {
    ("server/routes/segmentations.py", "create_segmentation"): "serializes zarr writes; the storage layer has no lock",
    ("server/routes/segmentations.py", "update_segmentation_data"): "serializes zarr writes; the storage layer has no lock",
    ("server/routes/segmentations.py", "update_model_segmentation_data"): "serializes zarr writes; the storage layer has no lock",
    ("server/routes/segmentations.py", "get_segmentation_data"): "blocks the loop deliberately -- serializes zarr access; the storage layer has no lock",
    ("server/routes/segmentations.py", "get_model_segmentation_data"): "blocks the loop deliberately -- serializes zarr access; the storage layer has no lock",
}


def _offenders_in(source: str, label: str) -> list[str]:
    return [
        f"{label}:{n.lineno} {n.name}"
        for n in _endpoints(ast.parse(source))
        if isinstance(n, ast.AsyncFunctionDef)
        and not _awaits_something(n)
        and (label, n.name) not in _MUST_STAY_ASYNC
    ]


def _scan() -> tuple[int, list[str], dict[tuple[str, str], type]]:
    """One walk of the routes: endpoint count, offenders, and each handler's def kind."""
    scanned = 0
    offenders: list[str] = []
    kinds: dict[tuple[str, str], type] = {}
    for path in sorted(_ROUTES.rglob("*.py")):
        source = path.read_text()
        label = f"server/routes/{path.relative_to(_ROUTES).as_posix()}"
        for node in _endpoints(ast.parse(source)):
            scanned += 1
            kinds[(label, node.name)] = type(node)
        offenders += _offenders_in(source, label)
    return scanned, offenders, kinds


def _pin_violations(
    kinds: dict[tuple[str, str], type],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Split _MUST_STAY_ASYNC into (entries naming no live handler, entries now def)."""
    missing = sorted(k for k in _MUST_STAY_ASYNC if k not in kinds)
    converted = sorted(
        k
        for k in _MUST_STAY_ASYNC
        if k in kinds and kinds[k] is not ast.AsyncFunctionDef
    )
    return missing, converted


def test_no_route_handler_is_async_without_awaiting():
    """Every async endpoint awaits; the rest are def and run in the threadpool."""
    scanned, offenders, _ = _scan()

    # Positive control: a walk that silently found nothing would pass an empty
    # offender list. Assert the scan actually reached the endpoints.
    assert scanned == 79, (
        f"expected 79 router-decorated endpoints, found {scanned}. If a route was "
        "deliberately added or removed, bump this number; if not, the walk is "
        "missing files and the empty offender list below proves nothing."
    )

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

    # A nested async helper's await belongs to the helper, not to the handler.
    nested = (
        "router = object()\n"
        "@router.get('/x')\n"
        "async def handler():\n"
        "    async def helper():\n"
        "        await thing()\n"
        "    return blocking_call()\n"
    )
    assert _offenders_in(nested, "fixture.py") == ["fixture.py:3 handler"]


def test_loop_bound_handlers_are_still_async():
    """Every handler declared loop-bound still exists and is still `async def`.

    The await guard above only exempts these; on its own that permits the
    opposite mistake. Three of the five await a request body, so they clear it
    whichever way they are declared, and nothing else in the suite would notice:
    test_route_concurrency.py drives `/task` and `/features`, neither of which
    touches the store. The consequence is silent -- concurrent zarr writes in the
    threadpool lose annotation data and still commit their row.
    """
    _, _, kinds = _scan()
    missing, converted = _pin_violations(kinds)

    assert not missing, (
        "these entries name a handler that no longer exists, so they document a "
        "constraint nothing enforces. Remove them, or correct the name:\n  "
        + "\n  ".join(f"{label} {name}" for label, name in missing)
    )

    assert not converted, (
        "these handlers must stay `async def` -- the event loop is the only thing "
        "serializing zarr access within a worker, and the storage layer has no "
        "lock. As `def` they run in the threadpool, where concurrent writes "
        "silently lose annotation data:\n  "
        + "\n  ".join(
            f"{label} {name}: {_MUST_STAY_ASYNC[(label, name)]}"
            for label, name in converted
        )
    )


def test_the_async_pin_can_fail():
    """Negative control: both halves of the pin must reject what they exist to catch.

    Driven off a synthetic kinds map rather than the real tree, so the control
    stays independent of the handlers under test.
    """
    pinned = sorted(_MUST_STAY_ASYNC)[0]
    all_async = {k: ast.AsyncFunctionDef for k in _MUST_STAY_ASYNC}

    assert _pin_violations(all_async) == ([], [])
    assert _pin_violations({**all_async, pinned: ast.FunctionDef}) == ([], [pinned])
    assert _pin_violations(
        {k: v for k, v in all_async.items() if k != pinned}
    ) == ([pinned], [])
