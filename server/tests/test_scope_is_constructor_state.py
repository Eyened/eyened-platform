"""A scope is constructor state, not a method parameter.

A per-method parameter is per-method forgettable: a repository method written
without it typechecks cleanly and is unscoped. A required constructor parameter
cannot be forgotten -- though it forces a scope to *exist*, not the right one,
and it filters nothing by itself. apply_scope is what filters; the coverage
test in test_repository_reads_are_scoped.py is what proves every read makes it.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

_REPOSITORIES = (
    pathlib.Path(__file__).resolve().parents[2] / "orm" / "eyened_orm" / "repositories"
)

# The one repository that builds the scope rather than consuming it.
_EXEMPT = {"ProjectMemberRepository"}


def _all_repository_classes() -> dict[str, type]:
    """Every class named *Repository, found by walking the package's modules.

    NOT ``package.__all__``: ``SearchRepository`` is imported from
    ``eyened_orm.repositories.search`` and is absent from that list, so an
    __all__-driven guard would silently skip the widest read surface in the
    API. An unexported repository is exactly the one that slips through.

    Shared with test_repository_reads_are_scoped.py, which validates its own
    allow-list against this same discovery.
    """
    import importlib
    import inspect
    import pkgutil

    import eyened_orm.repositories as package

    found: dict[str, type] = {}
    for module_info in pkgutil.walk_packages(
        package.__path__, prefix=f"{package.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if name.endswith("Repository") and cls.__module__.startswith(
                package.__name__
            ):
                found[name] = cls
    assert found, "guard found no repository classes -- it would pass vacuously"
    return found


def _repository_classes():
    return sorted(
        (name, cls)
        for name, cls in _all_repository_classes().items()
        if name not in _EXEMPT
    )


@pytest.mark.parametrize(
    "name,cls", _repository_classes(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_every_repository_requires_a_scope(name, cls):
    parameter = inspect.signature(cls.__init__).parameters.get("scope")
    assert parameter is not None, f"{name}.__init__ takes no scope"
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, f"{name}: scope must be keyword-only"
    assert parameter.default is inspect.Parameter.empty, f"{name}: scope must not default"


def test_no_repository_method_takes_a_scope_parameter():
    """Constructor state, not a per-method argument -- one or the other, never both."""
    offenders: list[str] = []
    for path in _REPOSITORIES.rglob("*.py"):
        if "__pycache__" in path.parts or path.name == "project_member_repository.py":
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name == "__init__":
                    continue
                names = [a.arg for a in item.args.args + item.args.kwonlyargs]
                if "scope" in names:
                    offenders.append(f"{path.name}::{node.name}.{item.name}")
    assert offenders == []


def test_every_service_factory_depends_on_get_access_scope():
    """The per-service factory is already the only place repositories are built.

    ``walk_packages``, not ``iter_modules``: the latter is non-recursive, so it
    never descends into ``server.services.search`` and ``get_search_service``
    -- the factory behind the widest read surface in the API -- was invisible
    to this guard. That is the same failure ``_all_repository_classes``'
    docstring warns about for repository discovery, and it is exactly how
    search would later ship unscoped. The ``__module__`` identity check below
    stays honest across the deeper path because ``walk_packages`` yields fully
    qualified names, so a subpackage ``__init__`` re-export is still skipped as
    the alias it is.
    """
    import importlib
    import pkgutil

    import server.services as services_package
    from server.services.access_scope import get_access_scope

    missing: list[str] = []
    for module_info in pkgutil.walk_packages(
        services_package.__path__, prefix=f"{services_package.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        for attr in dir(module):
            if not (attr.startswith("get_") and attr.endswith("_service")):
                continue
            if attr in {"get_audit_service"}:
                continue
            factory = getattr(module, attr)
            if not callable(factory) or factory.__module__ != module.__name__:
                continue
            defaults = [
                p.default for p in inspect.signature(factory).parameters.values()
            ]
            if not any(
                getattr(d, "dependency", None) is get_access_scope for d in defaults
            ):
                missing.append(f"{module.__name__}.{attr}")
    assert missing == []
