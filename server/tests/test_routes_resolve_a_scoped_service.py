"""Every route touching project data resolves its service through a scoped factory.

The complement to the repository guard: that one proves a read filters, this
one proves the route got a filtered repository in the first place. A route
added later that calls ``get_db`` directly and builds its own repository would
pass the first guard and fail this one.

The two exemption lists below are deliberately separate, because they are two
different claims. ``_NO_PROJECT_DATA`` says the route serves nothing a project
membership governs. ``_UNGATED_PROJECT_DATA`` says the opposite -- the route
does serve project data and is known to be unscoped today. Folding the second
into the first is how a guard turns an open hole into a documented guarantee.

Both lists, and the discovered-unscoped set they are checked against, are
keyed on ``f"{sorted(route.methods)} {route.path}"`` -- not on ``route.path``
alone. FastAPI can register a second route at the same path under a different
method (``DELETE /instances/images/{dataset_identifier:path}`` next to the
``GET`` already exempted here); keying on the path only would make that
second, unrelated route silently exempt too, with the set-equality ratchet
below still green.
"""
from __future__ import annotations

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from server.main import app_api
from server.services.access_scope import get_access_scope

# Routes that touch no project data. Each entry is a claim; keep it short.
# Keyed on method+path (see module docstring) so a second route sharing one
# of these paths under a different method is not silently exempt too.
_NO_PROJECT_DATA = {
    "['POST'] /auth/login",
    "['POST'] /auth/token",
    "['GET'] /auth/me",
    "['POST'] /auth/change-password",
    "['POST'] /auth/register",
    "['POST'] /auth/refresh",
    "['POST'] /auth/logout",
    "['GET'] /auth/options",
    "['GET'] /auth/oidc/authorize",
    "['POST'] /auth/oidc/authenticate",
}

# Routes that DO serve project data and resolve no scope. Not safe, not
# blessed -- listed so the guard states the truth rather than passing by
# silence, and so the next one added is a failure rather than a review finding.
# Keyed on method+path; see module docstring.
_UNGATED_PROJECT_DATA = {
    # Import: authenticated only. Gating these is a separate, planned task;
    # each entry leaves this list when that task wires the gate.
    "['POST'] /import/image",
    "['POST'] /import/run_cfi_amd",
    "['POST'] /import/run_cfi_models",
    "['POST'] /import/run_layer_segmentation",
    "['POST'] /import/update_thumbnails",
    "['POST'] /import/update_thumbnails_for_image_ids",
    "['GET'] /import/status/{task_id}",  # no authentication at all
    # Pixel data by storage path, served via X-Accel-Redirect. These touch no
    # Session at all -- the URL path *is* the identifier -- so there is no
    # service to make scoped without first resolving path -> ImageInstance.
    # An authenticated caller can fetch any project's pixels by path today.
    "['GET'] /instances/images/{dataset_identifier:path}",
    "['GET'] /instances/thumbnails/{thumbnail_identifier:path}",
}

_EXEMPT = _NO_PROJECT_DATA | _UNGATED_PROJECT_DATA

# Floor, not an exact pin: adding a properly scoped endpoint is routine, and a
# number bumped on every one of those stops being read. The floor catches the
# failure that matters here -- a discovery that collapses and checks nothing.
# The exact ratchet is test_the_exemption_lists_are_neither_stale_nor_wide.
_MINIMUM_ROUTES = 70


def _api_routes() -> list[APIRoute]:
    return [route for route in app_api.routes if isinstance(route, APIRoute)]


def _depends_on_scope(dependant: Dependant) -> bool:
    """True if get_access_scope appears anywhere in the route's dependency tree."""
    if dependant.call is get_access_scope:
        return True
    return any(_depends_on_scope(sub) for sub in dependant.dependencies)


def _route_key(route: APIRoute) -> str:
    return f"{sorted(route.methods)} {route.path}"


def _unscoped_keys() -> set[str]:
    return {
        _route_key(route)
        for route in _api_routes()
        if not _depends_on_scope(route.dependant)
    }


def test_every_project_data_route_resolves_a_scope():
    missing = sorted(
        _route_key(route)
        for route in _api_routes()
        if _route_key(route) not in _EXEMPT and not _depends_on_scope(route.dependant)
    )
    assert missing == []


def test_the_route_guard_saw_the_whole_route_table():
    """An empty route table would satisfy every assertion above by vacuity."""
    routes = _api_routes()
    assert len(routes) >= _MINIMUM_ROUTES, len(routes)


def test_the_exemption_lists_are_neither_stale_nor_wide():
    """Set equality both ways: a renamed route, and a route that got scoped.

    ``_EXEMPT`` minus the real table catches an entry left behind by a rename,
    which would silently un-guard the route it now fails to name. The table's
    unscoped set minus ``_EXEMPT`` is the same check the guard above makes.
    Equality also forces an entry *out* when its route is finally scoped, so
    the list shrinks instead of quietly outliving the hole it documented.
    """
    keys = {_route_key(route) for route in _api_routes()}
    assert _EXEMPT - keys == set()
    assert _unscoped_keys() == _EXEMPT


def test_the_two_exemption_lists_do_not_overlap():
    """One route, one claim -- an entry in both would make either unfalsifiable."""
    assert _NO_PROJECT_DATA & _UNGATED_PROJECT_DATA == set()
