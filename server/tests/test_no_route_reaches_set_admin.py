"""D5: no HTTP route reaches ``AccountAdministration.set_admin``.

Scans every registered endpoint, each dependency it resolves, and each class a
dependency returns. Bound: one hop -- a helper called from a service is not seen.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from server.main import app_api


def _calls(dependant: Dependant):
    yield dependant.call
    for sub in dependant.dependencies:
        yield from _calls(sub)


def _ours(obj: object) -> bool:
    return (getattr(obj, "__module__", None) or "").startswith(("server.", "eyened_orm"))


def _route_reachable_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for route in app_api.routes:
        if not isinstance(route, APIRoute):
            continue
        for call in _calls(route.dependant):
            if not (inspect.isfunction(call) or inspect.isclass(call)) or not _ours(call):
                continue
            sources[f"{call.__module__}.{call.__qualname__}"] = inspect.getsource(call)
            returned = inspect.signature(call, eval_str=True).return_annotation
            if inspect.isclass(returned) and _ours(returned):
                key = f"{returned.__module__}.{returned.__qualname__}"
                sources[key] = inspect.getsource(returned)
    return sources


def _names_set_admin(source: str) -> bool:
    return any(
        isinstance(node, ast.Attribute) and node.attr == "set_admin"
        for node in ast.walk(ast.parse(textwrap.dedent(source)))
    )


def test_no_route_reaches_set_admin():
    sources = _route_reachable_sources()

    # Positive controls: the walk reaches the admin service; the predicate fires.
    assert "server.services.admin_service.AdminService" in sources
    assert _names_set_admin("def f(self):\n    self.accounts.set_admin(username='x', is_admin=True)\n")

    assert [name for name, src in sources.items() if _names_set_admin(src)] == []
