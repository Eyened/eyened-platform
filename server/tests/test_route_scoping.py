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
