"""Search is the widest read surface; it filters like everything else."""
from __future__ import annotations

from datetime import date

import pytest

from eyened_orm.utils.factories import (
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
    scope_for,
)


@pytest.fixture()
def two_projects(session):
    """Project A and B, one patient/study/series/image each. Local to this file --
    the near-identical ORM-side fixture in test_repository_read_scoping.py lives in a
    different package with a different session fixture; duplication is deliberate."""
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    made = {}
    for name in ("A", "B"):
        project = make_project(session, name)
        patient = make_patient(session, project, f"pat-{name}")
        study = make_study(session, patient, date(2024, 1, 1))
        series = make_series(session, study)
        make_image(session, series, device, backend, f"img-{name}")
        made[name] = {"project": project.ProjectID, "study": study.StudyID}
    session.commit()
    return made


def test_instance_search_returns_only_in_scope_images(client_scoped, two_projects):
    client, set_scope = client_scoped
    set_scope(scope_for(two_projects["A"]["project"]))
    resp = client.post(
        "/instances/search",
        json={"conditions": [], "order_by": "Date Inserted", "order": "ASC"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Equality against result_ids, not `all(...)`: an empty list satisfies `all` and
    # would let a broken response shape pass as a scoping success.
    assert body["result_ids"] == ["img-A"]
    # Pins studies_by_ids: the response's "studies" block is derived from the
    # instances via studies_by_ids (search_service.py:209), and is NOT pinned by
    # result_ids alone -- see correction 9.
    assert [s["id"] for s in body["studies"]] == [two_projects["A"]["study"]]


def test_instance_search_sees_both_under_a_wider_scope(client_scoped, two_projects):
    """Pairs the hidden assertion above with a visible one under the wider scope."""
    client, set_scope = client_scoped
    set_scope(scope_for(two_projects["A"]["project"], two_projects["B"]["project"]))
    resp = client.post(
        "/instances/search",
        json={"conditions": [], "order_by": "Date Inserted", "order": "ASC"},
    )
    assert resp.status_code == 200
    assert resp.json()["result_ids"] == ["img-A", "img-B"]


def test_study_search_returns_only_in_scope_studies(client_scoped, two_projects):
    """search_studies and instances_for_studies both sit behind this route."""
    client, set_scope = client_scoped
    set_scope(scope_for(two_projects["A"]["project"]))
    resp = client.post(
        "/studies/search",
        json={"conditions": [], "order_by": "Study Date", "order": "ASC"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result_ids"] == [two_projects["A"]["study"]]
    # Pins instances_for_studies for THIS route's flow, but see correction 9:
    # this alone does not fail when instances_for_studies is unscoped, because
    # study_ids reaching it are already the A-only result of search_studies.
    assert [i["id"] for i in body["instances"]] == ["img-A"]


def test_search_counts_agree_with_the_filtered_rows(session, two_projects):
    """A count that ignores the scope leaks how much is being hidden."""
    from eyened_orm.repositories.search.repository import SearchRepository

    repo = SearchRepository(session, scope=scope_for(two_projects["A"]["project"]))
    assert repo.count_instances(conditions=[], attr_conditions=[], attr_defs={}) == 1
    assert repo.count_studies(conditions=[]) == 1

    both = SearchRepository(
        session,
        scope=scope_for(two_projects["A"]["project"], two_projects["B"]["project"]),
    )
    assert both.count_instances(conditions=[], attr_conditions=[], attr_defs={}) == 2
    assert both.count_studies(conditions=[]) == 2


def test_empty_scope_sees_nothing(session, two_projects):
    """Unlike Task/SubTask's vacuity, ImageInstance/Study are SINGLE_PROJECT_ENTITIES:
    zero memberships means zero visible rows, not a free pass."""
    from eyened_orm.repositories.search.repository import SearchRepository

    repo = SearchRepository(session, scope=scope_for())
    assert repo.count_instances(conditions=[], attr_conditions=[], attr_defs={}) == 0
    assert repo.count_studies(conditions=[]) == 0


def test_studies_by_ids_filters_out_of_scope_ids(session, two_projects):
    """Every caller of studies_by_ids today pre-filters its id list through an
    already-scoped search (correction 9), so a route test can't distinguish
    scoped from unscoped here -- only a direct call with a mixed id list can.
    This is the ONLY test that pins this method."""
    from eyened_orm.repositories.search.repository import SearchRepository

    repo = SearchRepository(session, scope=scope_for(two_projects["A"]["project"]))
    studies = repo.studies_by_ids(
        [two_projects["A"]["study"], two_projects["B"]["study"]]
    )
    assert [s.StudyID for s in studies] == [two_projects["A"]["study"]]


def test_instances_for_studies_filters_out_of_scope_ids(session, two_projects):
    """Same defense-in-depth situation as studies_by_ids above (correction 9)."""
    from eyened_orm.repositories.search.repository import SearchRepository

    repo = SearchRepository(session, scope=scope_for(two_projects["A"]["project"]))
    instances = repo.instances_for_studies(
        [two_projects["A"]["study"], two_projects["B"]["study"]]
    )
    assert [i.PublicID for i in instances] == ["img-A"]
