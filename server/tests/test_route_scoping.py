"""The scope reaches the HTTP boundary, and an invisible row is a 404 there.

Every other authorization test on this branch stops at the repository or at the
dependency in isolation; the `client` fixture hands all route tests an admin
scope, so nothing exercised request -> get_access_scope -> service ->
repository -> apply_scope -> 404 end to end. A filter that is correct in a unit
test and never reaches a handler is not enforcement.
"""
from __future__ import annotations

import pytest

from eyened_orm.utils.factories import make_patient, make_project, scope_for


@pytest.fixture()
def two_patients(session):
    """One patient in project A, one in project B."""
    made = {}
    for name in ("A", "B"):
        project = make_project(session, name)
        patient = make_patient(session, project, f"pat-{name}")
        made[name] = {"project": project.ProjectID, "patient": patient.PatientID}
    session.commit()
    return made


def test_a_patient_outside_the_scope_is_404_at_the_route(client_scoped, two_patients):
    """In scope: 200. Out of scope: 404 -- not 403, which would confirm it exists."""
    client, set_scope = client_scoped
    set_scope(scope_for(two_patients["A"]["project"]))

    visible = client.get(f"/patients/{two_patients['A']['patient']}")
    hidden = client.get(f"/patients/{two_patients['B']['patient']}")

    assert visible.status_code == 200
    assert hidden.status_code == 404


def test_an_empty_scope_sees_no_patient_at_all(client_scoped, two_patients):
    """A user with no memberships reads nothing -- and gets 404, not a 500.

    The empty-scope predicate is a distinct SQL shape (`IN (NULL) AND 1 != 1`),
    and AccessScope.project_ids raises for an administrator, so "no rows" is
    the one branch most likely to surface as an error rather than a 404.
    """
    client, set_scope = client_scoped
    set_scope(scope_for())

    assert client.get(f"/patients/{two_patients['A']['patient']}").status_code == 404
    assert client.get(f"/patients/{two_patients['B']['patient']}").status_code == 404


@pytest.fixture()
def authenticated_scoped(client_scoped):
    """`client_scoped` plus a satisfied `is_authenticated`.

    The pixel routes gate on `is_authenticated` (a decoded JWT) rather than on
    `get_current_user`, which is the only auth dependency `client_scoped`
    overrides. Without this the request never reaches the scope at all and a
    401 would pass an assertion meant to prove a 404.
    """
    from server.main import app_api
    from server.routes.auth import is_authenticated

    app_api.dependency_overrides[is_authenticated] = lambda: True
    yield client_scoped
    app_api.dependency_overrides.pop(is_authenticated, None)


@pytest.fixture()
def two_projects_images(session):
    """One stored image in project A, one in project B."""
    from datetime import datetime

    from eyened_orm.utils.factories import (
        make_device,
        make_image,
        make_series,
        make_storage_backend,
        make_study,
    )

    backend = make_storage_backend(session, "test-backend")
    device = make_device(session, "dev1")
    made = {}
    for name in ("A", "B"):
        project = make_project(session, name)
        patient = make_patient(session, project, f"pat-{name}")
        series = make_series(session, make_study(session, patient, datetime(2024, 1, 1)))
        image = make_image(
            session, series, device, backend, f"img-{name}", ThumbnailPath=f"thumb-{name}"
        )
        made[name] = {"project": project.ProjectID, "public_id": image.PublicID}
    session.commit()
    return made


def test_pixels_outside_the_scope_are_404_at_the_route(
    authenticated_scoped, two_projects_images
):
    """In scope the redirect is emitted; out of scope both pixel routes 404."""
    client, set_scope = authenticated_scoped
    set_scope(scope_for(two_projects_images["A"]["project"]))
    visible = two_projects_images["A"]["public_id"]
    hidden = two_projects_images["B"]["public_id"]

    ok_data = client.get(f"/images/{visible}/data")
    ok_thumb = client.get(f"/images/{visible}/thumbnail")

    assert ok_data.status_code == 200
    assert ok_data.headers["X-Accel-Redirect"] == "/test-backend/obj-img-A"
    assert ok_thumb.status_code == 200
    assert ok_thumb.headers["X-Accel-Redirect"] == "/thumbnails/thumb-A_144.jpg"

    assert client.get(f"/images/{hidden}/data").status_code == 404
    assert client.get(f"/images/{hidden}/thumbnail").status_code == 404


def test_an_empty_scope_is_served_no_pixels(authenticated_scoped, two_projects_images):
    """A user with no membership gets bytes for nothing -- 404, not a 500."""
    client, set_scope = authenticated_scoped
    set_scope(scope_for())

    for name in ("A", "B"):
        public_id = two_projects_images[name]["public_id"]
        assert client.get(f"/images/{public_id}/data").status_code == 404
        assert client.get(f"/images/{public_id}/thumbnail").status_code == 404


def test_the_by_path_pixel_routes_no_longer_exist(
    authenticated_scoped, two_projects_images
):
    """The unscoped by-path pair is gone, not merely unused.

    Deleting them is what closes the hole, so a re-added route must fail here
    as well as in the route-guard's set-equality ratchet.
    """
    client, set_scope = authenticated_scoped
    set_scope(scope_for(two_projects_images["A"]["project"]))

    assert client.get("/instances/images/ds-img-B").status_code == 404
    assert client.get("/instances/thumbnails/thumb-B_144.jpg").status_code == 404
