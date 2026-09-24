"""A scope is constructor state, not a method parameter.

A per-method parameter is per-method forgettable: a repository method written
without it typechecks cleanly and is unscoped. A required constructor parameter
cannot be forgotten -- though it forces a scope to *exist*, not the right one,
and it filters nothing by itself. apply_scope is what filters; a later coverage
guard is what will prove every read reaches it. Until that guard exists, the
behavioural proof is orm/eyened_orm/tests/test_repository_read_scoping.py,
which pins reads one at a time rather than exhaustively.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

_REPOSITORIES = (
    pathlib.Path(__file__).resolve().parents[2] / "orm" / "eyened_orm" / "repositories"
)
_SERVICES = pathlib.Path(__file__).resolve().parents[1] / "services"

# The one repository that builds the scope rather than consuming it.
_EXEMPT = {"ProjectMemberRepository"}

# Classes defined under repositories/ that are deliberately not repositories.
# Each entry is a claim that the class performs no reads of its own; a class
# that grows a query must be renamed rather than kept on this list.
_NOT_A_REPOSITORY = {
    "eyened_orm.repositories.search.conditions.AttributeConditionSpec",
    "eyened_orm.repositories.search.conditions.ResolvedCondition",
}

# Files under repositories/ whose functions may take a scope parameter:
# project_member_repository builds the scope, and _scoped is the shared helper
# every scoped read is routed through -- taking one is its entire purpose.
_SCOPE_PARAM_ALLOWED_FILES = {"project_member_repository.py", "_scoped.py"}


def _arg_names(args: ast.arguments) -> list[str]:
    """Every parameter name, including the forms a plain ``args`` read misses.

    ``posonlyargs``/``vararg``/``kwarg`` are not exotic: a guard that reads only
    ``args`` and ``kwonlyargs`` is silently blind to ``def m(self, scope, /)``
    and ``def m(self, **scope)``, both of which are the very thing being banned.
    """
    names = [
        a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)
    ]
    if args.vararg is not None:
        names.append(args.vararg.arg)
    if args.kwarg is not None:
        names.append(args.kwarg.arg)
    return names


def _functions(tree: ast.AST):
    """Every function in the module: methods, module-level, and nested.

    Descending only into ``ClassDef`` bodies -- the obvious shape -- cannot see
    a module-level helper or a function nested inside a method, so a banned
    parameter simply moves one level to escape the guard.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _all_repository_classes() -> dict[str, type]:
    """Every class named *Repository, found by walking the package's modules.

    NOT ``package.__all__``: ``SearchRepository`` is imported from
    ``eyened_orm.repositories.search`` and is absent from that list, so an
    __all__-driven guard would silently skip the widest read surface in the
    API. An unexported repository is exactly the one that slips through.

    Keyed by ``module.ClassName``: two same-named classes in different modules
    would otherwise collide and one would go unchecked.
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
                found[f"{cls.__module__}.{name}"] = cls
    assert found, "guard found no repository classes -- it would pass vacuously"
    return found


def _repository_classes():
    return sorted(
        (qualname, cls)
        for qualname, cls in _all_repository_classes().items()
        if cls.__name__ not in _EXEMPT
    )


def test_every_class_under_repositories_is_named_repository():
    """Discovery is by name, so a class that breaks the convention is invisible.

    ``_all_repository_classes`` -- and every guard built on it -- finds classes
    by the *Repository suffix. A read surface named anything else passes every
    scope guard in this file without ever being looked at, so the naming
    convention is load-bearing and has to be enforced rather than assumed.
    """
    import importlib
    import inspect
    import pkgutil

    import eyened_orm.repositories as package

    unconventional: list[str] = []
    for module_info in pkgutil.walk_packages(
        package.__path__, prefix=f"{package.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if not cls.__module__.startswith(package.__name__):
                continue
            qualname = f"{cls.__module__}.{name}"
            if name.endswith("Repository") or qualname in _NOT_A_REPOSITORY:
                continue
            unconventional.append(qualname)
    assert unconventional == []


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
    assert _REPOSITORIES.is_dir(), (
        f"{_REPOSITORIES} is not a directory -- rglob() would yield nothing and "
        "this guard would pass vacuously"
    )
    offenders: list[str] = []
    for path in _REPOSITORIES.rglob("*.py"):
        if "__pycache__" in path.parts or path.name in _SCOPE_PARAM_ALLOWED_FILES:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for item in _functions(tree):
            if item.name == "__init__":
                continue
            if "scope" in _arg_names(item.args):
                offenders.append(f"{path.name}::{item.name}")
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


def _resolved_scope_parameter(factory: ast.FunctionDef) -> str | None:
    """The parameter name bound to ``Depends(get_access_scope)``, if any."""
    defaulted = list(
        zip(
            factory.args.args[len(factory.args.args) - len(factory.args.defaults) :],
            factory.args.defaults,
        )
    ) + [
        (arg, default)
        for arg, default in zip(factory.args.kwonlyargs, factory.args.kw_defaults)
        if default is not None
    ]
    for arg, default in defaulted:
        if (
            isinstance(default, ast.Call)
            and isinstance(default.func, ast.Name)
            and default.func.id == "Depends"
            and default.args
            and isinstance(default.args[0], ast.Name)
            and default.args[0].id == "get_access_scope"
        ):
            return arg.arg
    return None


def test_every_service_factory_threads_its_resolved_scope():
    """Declaring the dependency is not the same as passing it on.

    ``test_every_service_factory_depends_on_get_access_scope`` proves a factory
    *resolves* a scope; nothing proved it hands that same scope to the objects
    it builds. A factory that resolves the caller's scope and then constructs
    ``PatientRepository(db, scope=AccessScope.trusted())`` keeps the whole suite
    green while serving every project's data on that endpoint -- apply_scope
    short-circuits on is_admin, so the read is not filtered at all.
    """
    assert _SERVICES.is_dir(), (
        f"{_SERVICES} is not a directory -- this guard would pass vacuously"
    )
    offenders: list[str] = []
    for path in _SERVICES.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for factory in _functions(tree):
            if not (
                factory.name.startswith("get_") and factory.name.endswith("_service")
            ):
                continue
            scope_param = _resolved_scope_parameter(factory)
            if scope_param is None:
                # No resolved scope to thread; the guard above owns that case.
                continue
            where = f"{path.name}::{factory.name}"
            for node in ast.walk(factory):
                if isinstance(node, ast.Name) and node.id == "admin_scope":
                    offenders.append(f"{where} names admin_scope")
                if isinstance(node, ast.Attribute) and node.attr == "trusted":
                    offenders.append(f"{where} names AccessScope.trusted")
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                    continue
                callee = node.func.id
                if not (
                    callee.endswith("Repository") or callee.endswith("Service")
                ):
                    continue
                passed = {
                    kw.arg: kw.value for kw in node.keywords if kw.arg == "scope"
                }
                value = passed.get("scope")
                if value is None:
                    offenders.append(f"{where} builds {callee} with no scope=")
                elif not (isinstance(value, ast.Name) and value.id == scope_param):
                    offenders.append(
                        f"{where} builds {callee} with a scope other than {scope_param}"
                    )
    assert offenders == []


def test_no_service_method_takes_an_actor_parameter():
    """One source of actor identity per call. Two can disagree.

    server/routes/auth.py and import_api.py still build an ActingUser by hand:
    they call AuditService directly rather than through a scoped service, so
    there is no scope to derive it from.
    """
    assert _SERVICES.is_dir(), (
        f"{_SERVICES} is not a directory -- this guard would pass vacuously"
    )
    offenders: list[str] = []
    for path in _SERVICES.rglob("*.py"):
        # Path-relative, not by basename: a nested services/**/audit_service.py
        # would otherwise inherit the one exclusion this guard grants.
        if "__pycache__" in path.parts or path.relative_to(_SERVICES) == pathlib.Path(
            "audit_service.py"
        ):
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for item in _functions(tree):
            if "actor" in _arg_names(item.args):
                offenders.append(f"{path.name}::{item.name}")
    assert offenders == []
