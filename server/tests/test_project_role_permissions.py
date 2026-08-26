"""Role floors for the v0.3 permission rows nothing else reaches.

Most rows are already covered by the task that implemented the floor, through
the same routes and fixtures these tests use, so this file does not restate
them. The row-by-role coverage map lives in the plan, not here: a table of test
names in the test suite checks that strings still occur in files, not that
anything is enforced.

Every row left uncovered turned out to be a **positive** cell, and that is the
finding. The suite is dense on refusals and thin on permissions -- an
enforcement layer that denied everything would pass almost all of it. These
tests are the other direction: the roles v0.3 grants must actually be granted.

"Create/delete tasks" is split: the delete half is a normal case below, and the
create half is test_anyone_can_create_a_task in test_task_write_floors.py,
because a new task touches no projects and creation is therefore unrestricted
for every role.
"""
from __future__ import annotations

import json

import pytest

from eyened_orm.authz.roles import ProjectRole
from eyened_orm.utils.factories import scope_for

_R, _G, _PA = ProjectRole.read_only, ProjectRole.grader, ProjectRole.project_admin


@pytest.fixture()
def fake_segmentation_store(monkeypatch):
    """dependency_overrides cannot reach this: get_segmentation_service calls
    get_segmentation_data_store() directly, so the name in that module is the
    seam. Without it the create path reaches /storage and dies on the host."""
    import numpy as np

    import server.services.segmentation_service as seg_service

    class _Fake:
        def read(self, segmentation, *, axis=None, slice_index=None):
            return np.zeros((1, 4, 4), dtype="uint8")

        def write(self, segmentation, data, *, axis=None, slice_index=None):
            return int(np.asarray(data).size)

    monkeypatch.setattr(seg_service, "get_segmentation_data_store", lambda: _Fake())


# --- G1: view project data -------------------------------------------------
#
# The id here is the ImageInstanceID **integer**. /instances/{instance_id} is
# the one route in this file typed int; the tag routes beside it and
# /images/{image_id} take the PublicID string, and passing the wrong one gets a
# 422 that looks nothing like an authorization result.


@pytest.mark.parametrize("role", [_R, _G, _PA], ids=lambda r: r.name)
def test_every_member_role_reads_project_data(client_scoped, one_project, role):
    """G1: the floor for reads is membership, not privilege."""
    client, set_scope = client_scoped
    set_scope(one_project.scope(role))
    assert client.get(f"/instances/{one_project.image}").status_code == 200


def test_a_non_member_cannot_read_project_data(client_scoped, one_project):
    """G1's control: without the membership the same read is 404, so the three
    cases above are pinning the membership and not merely a reachable route."""
    client, set_scope = client_scoped
    set_scope(scope_for(actor_id=one_project.actor))
    assert client.get(f"/instances/{one_project.image}").status_code == 404


# --- G2: create annotations ------------------------------------------------


@pytest.mark.parametrize("role", [_G, _PA], ids=lambda r: r.name)
def test_a_grader_or_project_admin_creates_an_annotation(
    client_scoped, one_project, fake_segmentation_store, role
):
    """G2: creating annotations is a grader floor, not an admin one."""
    client, set_scope = client_scoped
    set_scope(one_project.scope(role))
    resp = client.post(
        "/segmentations",
        data={
            "metadata": json.dumps(
                {
                    "image_id": one_project.public_id,
                    "depth": 1,
                    "height": 4,
                    "width": 4,
                    "data_type": "R8UI",
                    "data_representation": "Binary",
                    "feature_id": one_project.feature,
                }
            )
        },
    )
    assert resp.status_code == 200, resp.text


# --- G3: delete own annotation ---------------------------------------------


def test_a_grader_deletes_their_own_annotation(client_scoped, one_project):
    """G3: a grader needs no project_admin role to retract their own work."""
    client, set_scope = client_scoped
    set_scope(one_project.scope(_G))
    assert client.delete(
        f"/segmentations/{one_project.own_segmentation}"
    ).status_code == 204


# --- G4: update subtask grading status --------------------------------------


def test_a_grader_updates_a_subtask_grading_status(client_scoped, one_project):
    """G4: marking a subtask graded is the grader's own workflow, not admin's."""
    client, set_scope = client_scoped
    set_scope(one_project.scope(_G))
    resp = client.patch(
        f"/subtasks/{one_project.subtask}", json={"task_state": "Ready"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["task_state"] == "Ready"


# --- G5: delete a populated task --------------------------------------------


def test_a_project_admin_deletes_a_populated_task(client_scoped, one_project):
    """G5: the role above the grader that test_grader_cannot_delete_a_populated
    _task refuses must actually be able to delete it."""
    client, set_scope = client_scoped
    set_scope(one_project.scope(_PA))
    assert client.delete(f"/task/{one_project.task}").status_code == 204


# --- G6: view annotation author identity ------------------------------------


@pytest.mark.parametrize("role", [_R, _G, _PA], ids=lambda r: r.name)
def test_every_member_role_sees_another_users_annotation_author(
    client_scoped, one_project, role
):
    """G6 (v0.3 L202): author identity is readable by every member role.

    Read on a **stranger's** row: the caller's own name would come back either
    way, so only a foreign author shows the identity is actually disclosed.
    """
    client, set_scope = client_scoped
    set_scope(one_project.scope(role))
    resp = client.get(f"/segmentations/{one_project.foreign_segmentation}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["creator"]["name"] == "other"


# --- The real dependency chain ----------------------------------------------
#
# Every other authorization test in the suite overrides get_access_scope. That
# is right for the enforcement tests -- they need to *set* a scope -- but it
# means nothing else joins JWT -> get_current_user -> get_access_scope ->
# repository filter through the real dependency graph. A mis-wired Depends in a
# service factory would pass every one of them and fail in production.


@pytest.fixture()
def two_projects(session):
    """One image in each of two projects, for the chain test below.

    File-local on purpose. Three other files carry their own ``two_projects``,
    each with a standing comment saying the duplication is deliberate, and none
    of them exposes what this test reads.
    """
    from datetime import date

    from eyened_orm.utils.factories import (
        make_device,
        make_image,
        make_patient,
        make_project,
        make_series,
        make_storage_backend,
        make_study,
    )

    backend = make_storage_backend(session)
    device = make_device(session, "d")
    out = {}
    for name in ("A", "B"):
        project = make_project(session, f"proj-{name}")
        patient = make_patient(session, project, f"pat-{name}")
        study = make_study(session, patient, date(2024, 1, 1))
        series = make_series(session, study)
        image = make_image(session, series, device, backend, f"img-{name}")
        # Ids read out before the commit: expire_on_commit=True.
        out[name] = {"project": project.ProjectID, "image": image.ImageInstanceID}
    session.commit()
    return out


def test_the_real_dependency_chain_filters_a_logged_in_users_reads(
    session, signed_jwts, two_projects, monkeypatch
):
    """No dependency overrides at all: log in, then read.

    The one test that proves get_access_scope is actually wired into the
    factories, rather than that the filter works when a scope is handed to it.
    """
    from fastapi.testclient import TestClient

    import server.db as server_db
    from eyened_orm.authz.roles import ProjectRole
    from eyened_orm.repositories.project_member_repository import (
        ProjectMemberRepository,
    )
    from eyened_orm.utils.db_users import create_user
    from server.main import app_api
    from server.services.access_scope import get_access_scope
    from server.tests.conftest import _SessionBoundDatabase

    # app_api.dependency_overrides is module-level singleton state, and this
    # test asserts this one override's *absence*: a leak from another fixture
    # would let it pass while proving nothing about the chain. Targeted rather
    # than blanket -- an unrelated override says nothing about this chain, and
    # failing on it would make the suite's other fixtures this test's business.
    assert get_access_scope not in app_api.dependency_overrides, (
        "an override leaked from another fixture; the chain cannot be observed"
    )

    alice = create_user(session, "alice", "pw")
    ProjectMemberRepository(session).upsert(
        alice.CreatorID, two_projects["A"]["project"], ProjectRole.grader
    )
    session.commit()

    monkeypatch.setattr(server_db, "database", _SessionBoundDatabase(session))

    with TestClient(app_api) as client:
        login = client.post(
            "/auth/token", json={"username": "alice", "password": "pw"}
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # The integer id again -- the same 422 trap as the cells above.
        assert client.get(
            f"/instances/{two_projects['A']['image']}", headers=headers
        ).status_code == 200
        assert client.get(
            f"/instances/{two_projects['B']['image']}", headers=headers
        ).status_code == 404
