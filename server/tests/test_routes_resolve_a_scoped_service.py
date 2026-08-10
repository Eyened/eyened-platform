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
"""
from __future__ import annotations

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from server.main import app_api
from server.services.access_scope import get_access_scope

# Routes that touch no project data. Each entry is a claim; keep it short.
_NO_PROJECT_DATA = {
    "/auth/login",
    "/auth/token",
    "/auth/me",
    "/auth/change-password",
    "/auth/register",
    "/auth/refresh",
    "/auth/logout",
    "/auth/options",
    "/auth/oidc/authorize",
    "/auth/oidc/authenticate",
}

# Routes that DO serve project data and resolve no scope. Not safe, not
# blessed -- listed so the guard states the truth rather than passing by
# silence, and so the next one added is a failure rather than a review finding.
_UNGATED_PROJECT_DATA = {
    # Import: authenticated only. Gating these is a separate, planned task;
    # each entry leaves this list when that task wires the gate.
    "/import/image",
    "/import/run_cfi_amd",
    "/import/run_cfi_models",
    "/import/run_layer_segmentation",
    "/import/update_thumbnails",
    "/import/update_thumbnails_for_image_ids",
    "/import/status/{task_id}",  # no authentication at all
    # Pixel data by storage path, served via X-Accel-Redirect. These touch no
    # Session at all -- the URL path *is* the identifier -- so there is no
    # service to make scoped without first resolving path -> ImageInstance.
    # An authenticated caller can fetch any project's pixels by path today.
    "/instances/images/{dataset_identifier:path}",
    "/instances/thumbnails/{thumbnail_identifier:path}",
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


def _unscoped_paths() -> set[str]:
    return {
        route.path for route in _api_routes() if not _depends_on_scope(route.dependant)
    }


def test_every_project_data_route_resolves_a_scope():
    missing = sorted(
        f"{sorted(route.methods)} {route.path}"
        for route in _api_routes()
        if route.path not in _EXEMPT and not _depends_on_scope(route.dependant)
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
    paths = {route.path for route in _api_routes()}
    assert _EXEMPT - paths == set()
    assert _unscoped_paths() == _EXEMPT


def test_the_two_exemption_lists_do_not_overlap():
    """One route, one claim -- an entry in both would make either unfalsifiable."""
    assert _NO_PROJECT_DATA & _UNGATED_PROJECT_DATA == set()
