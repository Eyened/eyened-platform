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
        if takes_ids and enqueues and "require_grader_on_images" not in body_names:
            ungated.append(node.name)
    assert ungated == []


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
    # fails closed and prompts a look; narrowing the walk is not worth it. A
    # function with no `return` at all passes, correctly: `job.result` is then
    # None, which discloses nothing.
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
