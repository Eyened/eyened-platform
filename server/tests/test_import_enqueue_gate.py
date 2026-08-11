"""The enqueue call is the boundary: an unchecked enqueue launders a write."""
from __future__ import annotations

import ast
import pathlib
from datetime import date

import pytest

from eyened_orm.authz.roles import ProjectRole
from eyened_orm.utils.factories import (
    admin_scope,
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
    scope_for,
)

# All four by-id enqueue routes share one gate helper. The behaviour is tested
# once, on a representative route; what proves the other three are gated is
# test_every_route_enqueueing_over_caller_supplied_ids_is_gated below, which
# asserts the *set*. Parametrizing the three behaviour tests over all four
# would run the same helper twelve times and still not catch a fifth route.
_GATED = "/import/run_cfi_models"

# FastAPI's default 404 handler answers an unrouted path with "Not Found"
# (capital F); an authz denial answers with "Not found" (_AUTHZ_BODY in
# server/services/exceptions.py). Asserting the status alone therefore cannot
# tell a gated route from a route that does not exist -- a typo in
# _BY_IDS_ROUTES would keep every case below green. Asserting this exact body
# is what proves the route is live *and* denying.
#
# That body check degrades silently if a future StarletteHTTPException handler
# normalizes the route-miss body to the same "Not found" string -- see
# test_by_ids_routes_are_registered below for the control that catches that.
_DENIAL_BODY = {"detail": "Not found"}

# The one exception to that, and the reason it is an exception: the set test
# cannot see gate *ordering* -- a gate moved inside a route's `try:` still has
# the name `require_grader_on_images` in its body, so the AST check stays
# green while the denial turns into a 200 with success=False. Ordering is
# per-route, and post_import_update_thumbnails_for_image_ids holds a `try:` of
# its own, so only a behaviour test on that route can catch it. The 404 case
# is parametrized over all four for that reason; the 200 and 403 cases stay on
# _GATED, where a second copy would only re-run the same helper.
_BY_IDS_ROUTES = [
    "/import/run_cfi_models",
    "/import/run_cfi_amd",
    "/import/run_layer_segmentation",
    "/import/update_thumbnails_for_image_ids",
]


def test_by_ids_routes_are_registered():
    """The route-existence control the body assertion above cannot provide.

    _DENIAL_BODY currently doubles as proof that a 404 came from a live,
    denying route rather than a route that does not exist -- see the comment
    on _DENIAL_BODY. That proof depends on the two 404 bodies staying
    distinguishable; a future StarletteHTTPException handler that normalizes
    the route-miss body to the same "Not found" string would make them
    identical, and every parametrized case in
    test_one_out_of_scope_id_refuses_the_whole_batch would keep passing
    against a nonexistent path with nothing anywhere failing. This asserts
    registration directly, so it cannot be invalidated by a body-format
    change: independent of the response the routes ever produce.

    A standalone test rather than folded into the parametrized one: it is a
    single fact about the app's route table, not per-route behaviour, and
    doesn't need `client_scoped`/`two_projects`/a request round-trip to check.
    """
    from server.main import app_api

    assert set(_BY_IDS_ROUTES) <= {r.path for r in app_api.routes}


@pytest.fixture()
def two_projects(session):
    """Project A and B, one patient/study/series/image each.

    Local to this file, like every other two-project fixture in the suite --
    see the note at test_search_scoping.py:21 on why the duplication is
    deliberate. This one keeps the ImageInstanceID, which the search-side
    copy discards, because the gate under test takes raw image ids.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    # Burn ProjectIDs so the two id spaces cannot coincide. One project per
    # image otherwise numbers both 1, 2, and the gate's resolver returning
    # {project_id: image_id} -- the mapping inverted -- passes every test in
    # this file. In production image ids dwarf project ids, so that inversion
    # would leave `set(image_ids) - set(by_image)` non-empty and 404 every
    # enqueue; these throwaway rows are what lets a test see it. Do not
    # simplify them away.
    for i in range(3):
        make_project(session, f"spacer-{i}")
    made = {}
    for name in ("A", "B"):
        project = make_project(session, name)
        patient = make_patient(session, project, f"pat-{name}")
        study = make_study(session, patient, date(2024, 1, 1))
        series = make_series(session, study)
        image = make_image(session, series, device, backend, f"img-{name}")
        # Read the id out before the commit: expire_on_commit=True.
        made[name] = {"project": project.ProjectID, "image": image.ImageInstanceID}
    session.commit()
    # The offset actually landed, rather than assumed: a later edit dropping the
    # spacer rows fails here instead of quietly re-blinding every test below.
    assert {row["project"] for row in made.values()}.isdisjoint(
        {row["image"] for row in made.values()}
    )
    return made


@pytest.mark.parametrize("route", _BY_IDS_ROUTES)
def test_one_out_of_scope_id_refuses_the_whole_batch(
    client_scoped, two_projects, queue_spy, route
):
    """The negative case is the one that matters.

    A single out-of-scope id fails the whole request rather than being silently
    dropped, so partial success cannot be used to probe which ids exist. This
    deliberately inverts the usual batch rule of collecting per-item successes
    and failures -- here the per-item outcome *is* the leak, since "your batch
    of 50 ran but item 37 didn't" tells the caller precisely which ids they
    cannot see. Recorded so a later reviewer applying the general pattern does
    not "fix" it.

    Parametrized over all four by-ids routes rather than run on _GATED alone:
    this is the case that pins gate *ordering*, which the AST set test below
    structurally cannot see.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(two_projects["A"]["project"], role=ProjectRole.grader))
    resp = client.post(
        route,
        json={"image_ids": [two_projects["A"]["image"], two_projects["B"]["image"]]},
    )
    assert resp.status_code == 404
    # Body, not just status: see _DENIAL_BODY. Without this, three of these
    # four cases pass against a route that does not exist.
    assert resp.json() == _DENIAL_BODY
    assert queue_spy.enqueued == []


def test_an_unknown_id_in_the_batch_refuses_the_whole_batch(
    client_scoped, two_projects, queue_spy
):
    """The mixed batch is the point: one visible id, one id that resolves to no image.

    A batch where every id resolves cannot reach the unknown-id branch at all --
    `scope.require` produces the 404 on its own from the resolved project set,
    so the test above (two real images, one out of scope) leaves that branch
    dead. Only a batch that is *partly* resolvable exercises it, and without it
    a grader posting [visible_id, 999999] would get a 200 while
    [visible_id, other_project_id] gets a 404 -- an existence oracle for ids the
    actor cannot see.
    """
    client, set_scope = client_scoped
    set_scope(scope_for(two_projects["A"]["project"], role=ProjectRole.grader))
    resp = client.post(
        _GATED,
        json={"image_ids": [two_projects["A"]["image"], 999999]},
    )
    assert resp.status_code == 404
    assert resp.json() == _DENIAL_BODY
    assert queue_spy.enqueued == []


def test_an_unknown_id_in_the_batch_refuses_an_admin_too(
    client_scoped, two_projects, queue_spy
):
    """require_grader_on_images's unknown-id pre-check runs before scope.require,
    so it fails the batch for *every* caller -- admin included (see the
    docstring on image_instance_service.require_grader_on_images). Nothing
    above exercises the admin path through this method: every other case in
    this file scopes the client to a project role. Without this test, an
    ``if self.scope.is_admin: return`` short-circuit added at the top of
    require_grader_on_images -- the obvious "fix" for the maintenance-workflow
    complaint the docstring anticipates -- would flip that guarantee and fail
    nothing here.
    """
    client, set_scope = client_scoped
    set_scope(admin_scope())
    resp = client.post(
        _GATED,
        json={"image_ids": [two_projects["A"]["image"], 999999]},
    )
    assert resp.status_code == 404
    assert resp.json() == _DENIAL_BODY
    assert queue_spy.enqueued == []


def test_a_grader_on_every_id_may_enqueue(client_scoped, two_projects, queue_spy):
    client, set_scope = client_scoped
    set_scope(scope_for(two_projects["A"]["project"], role=ProjectRole.grader))
    resp = client.post(_GATED, json={"image_ids": [two_projects["A"]["image"]]})
    assert resp.status_code == 200
    assert queue_spy.enqueued


def test_a_read_only_member_may_not_enqueue(client_scoped, two_projects, queue_spy):
    """v0.3: run model inference on accessible project images -- grader role."""
    client, set_scope = client_scoped
    set_scope(scope_for(two_projects["A"]["project"], role=ProjectRole.read_only))
    resp = client.post(_GATED, json={"image_ids": [two_projects["A"]["image"]]})
    assert resp.status_code == 403
    assert queue_spy.enqueued == []


def test_the_whole_database_thumbnail_sweep_is_admin_only(
    client_scoped, two_projects, queue_spy
):
    client, set_scope = client_scoped
    set_scope(scope_for(two_projects["A"]["project"], role=ProjectRole.project_admin))
    assert client.post("/import/update_thumbnails").status_code == 403
    assert queue_spy.enqueued == []
    set_scope(admin_scope())
    assert client.post("/import/update_thumbnails").status_code == 200
    assert queue_spy.enqueued


def test_importing_an_image_is_admin_only(client_scoped, two_projects):
    client, set_scope = client_scoped
    set_scope(scope_for(two_projects["A"]["project"], role=ProjectRole.project_admin))
    # `options` is required on ImportRequest (no default), and FastAPI
    # validates the body during dependency solving -- before the handler runs.
    # Omitting it gets a 422 that never reaches the gate under test.
    resp = client.post(
        "/import/image", json={"data": {"project_name": "A"}, "options": {}}
    )
    assert resp.status_code == 403


def test_every_route_enqueueing_over_caller_supplied_ids_is_gated():
    """Asserts the *set*, not a hand-written list of three.

    A fifth such route added later fails the suite instead of shipping open --
    which is exactly how the two thumbnail routes were nearly missed.
    """
    source = pathlib.Path(__file__).resolve().parents[1] / "routes" / "import_api.py"
    tree = ast.parse(source.read_text(), filename=str(source))
    discovered: list[str] = []
    ungated: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body_names = {
            n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)
        } | {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        takes_ids = any(
            isinstance(n, ast.Attribute) and n.attr == "image_ids"
            for n in ast.walk(node)
        )
        enqueues = "enqueue" in body_names or "_queue_rq_job" in body_names
        if not (takes_ids and enqueues):
            continue
        discovered.append(node.name)
        if "require_grader_on_images" not in body_names:
            ungated.append(node.name)
    # Anti-vacuity, in the same style as test_every_rq_entrypoint_returns_a_bare_bool
    # below: `ungated == []` also passes when discovery finds nothing at all, and
    # import_api.py is slated for deprecation -- an enqueue route moved to a new
    # module would leave this hardcoded path empty and the suite green. A name-set
    # floor rather than a count: the four names are stable, and a rename that
    # relocates a gate is itself worth a failure.
    assert set(discovered) >= {
        "enqueue_run_cfi_models",
        "enqueue_run_cfi_amd",
        "enqueue_run_layer_segmentation",
        "post_import_update_thumbnails_for_image_ids",
    }
    assert ungated == []


def test_the_batch_gate_resolves_projects_through_the_shared_helper():
    """The gate's project resolution is not allowed to grow a second join chain.

    ``_PARENT_OF`` (orm/eyened_orm/authz/scoping.py) is the one place an image's
    route to its ``Project`` is written down, and the read filters are built
    from it. A gate that re-forks that route into its own hand-written join
    resolves projects by a copy that a later change to the route -- a
    denormalized column, an anchor move, a predicate added to a hop -- silently
    leaves stale, while every read moves.

    Structural rather than behavioural because behaviour cannot see it: the
    fork and the shared helper emit identical SQL today, so the ORM-side
    agreement test (test_image_instance_repository.py) passes on either. Only
    the *shape* of the method distinguishes them, and that is what this reads.
    Both directions are asserted -- the helper is called, and no query is built
    locally -- because either alone admits a body that calls the helper and then
    ignores it.
    """
    source = (
        pathlib.Path(__file__).resolve().parents[2]
        / "orm"
        / "eyened_orm"
        / "repositories"
        / "image_instance_repository.py"
    )
    tree = ast.parse(source.read_text(), filename=str(source))
    bodies = [
        item
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "ImageInstanceRepository"
        for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == "project_ids_for_images"
    ]
    # Anti-vacuity: a rename or a move would otherwise leave the two assertions
    # below iterating over nothing and reporting green on an unguarded method.
    assert len(bodies) == 1, source

    called = {
        call.func.id if isinstance(call.func, ast.Name) else call.func.attr
        for call in ast.walk(bodies[0])
        if isinstance(call, ast.Call)
        and isinstance(call.func, (ast.Name, ast.Attribute))
    }
    assert "image_project_pairs" in called, sorted(called)
    assert called & {"select", "select_from", "join", "outerjoin", "join_from"} == set()


def test_every_rq_entrypoint_returns_a_bare_bool():
    """`GET /import/status/{task_id}` hands `job.result` to its caller.

    Every entrypoint returns True today, so the response carries no project
    data. A job that later returns a summary -- processed ids, per-image errors
    -- would publish it through that route without a single test failing.

    The `-> bool` annotations added alongside this are documentation, not
    enforcement: mypy is not a CI gate here, so an annotation that lies about a
    dict return would pass unnoticed. This AST check is what enforces.

    Entrypoints are found by the `run_*` convention rather than derived from
    the enqueue call sites, which is the weaker of the two and is a deliberate
    choice: `_queue_rq_job` (import_api.py) takes the function as a parameter,
    so an AST walk over `.enqueue(...)` resolves the local name `func` for two
    of the five and would silently cover only three. The floor assertion below
    is what keeps the convention honest; the rule itself is written into the
    module docstring of tasks.py, where an author adding a sixth job will read
    it.
    """
    source = pathlib.Path(__file__).resolve().parents[1] / "utils" / "tasks.py"
    tree = ast.parse(source.read_text(), filename=str(source))
    entrypoints = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("run_")
    ]
    # Anti-vacuity: a discovery that collapses to [] would assert nothing.
    assert {node.name for node in entrypoints} >= {
        "run_thumbnail_update_job",
        "run_thumbnail_update_for_image_ids_job",
        "run_cfi_model_for_image_ids",
        "run_cfi_amd_for_image_ids",
        "run_layer_segmentation_for_image_ids",
    }
    # `ast.walk` descends into nested defs, so a future closure returning a
    # non-bool flags its enclosing entrypoint. That is a false positive, but it
    # fails closed and prompts a look; narrowing the walk is not worth it.
    # A function with no `return` *statement* passes, correctly: `job.result` is
    # then None, which discloses nothing. A written-out `return` or
    # `return None` is flagged even though it discloses nothing either
    # (`ast.Return.value` is None / `Constant(None)`, and neither is a bool
    # constant). That second false positive is kept rather than excluded: the
    # predicate stays "every return is a literal bool", which is the rule the
    # tasks.py docstring states, and widening it to admit None would also admit
    # a `return None` that a later edit turns into `return summary`.
    leaky = [
        node.name
        for node in entrypoints
        for stmt in ast.walk(node)
        if isinstance(stmt, ast.Return)
        and not (
            isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, bool)
        )
    ]
    assert leaky == []


def test_the_status_route_requires_authentication(client_anonymous):
    """401, from get_current_user's final raise (server/services/current_user.py).

    Uses `client_anonymous` rather than `client`/`client_scoped`: both of those
    override get_current_user, so neither can ever observe this case.
    """
    assert client_anonymous.get("/import/status/any-id").status_code == 401
