"""External data sources: proxied through the API, scoped by the study's project.

The upstream is never reachable from the browser, so these routes are the only
access path; a study the actor cannot see must not reach the upstream at all.
"""
from __future__ import annotations

from datetime import date

import httpxyz
import pytest

import server.services.study_service as study_service
from eyened_orm.utils.factories import make_patient, make_project, make_study, scope_for
from server.config import DATA_SOURCES_PATH, DataSource, load_data_sources

REGISTRY = DataSource(
    name="Registry",
    url="http://upstream:5000/api/project/{project}/patient/{patient}/study/{date}",
    projects=["Alpha"],
    collapse=True,
)
BODY = b'{"table": [["a", 1]]}'


@pytest.fixture()
def sources(monkeypatch):
    monkeypatch.setattr(study_service, "get_data_sources", lambda: (REGISTRY,))


@pytest.fixture()
def upstream(monkeypatch):
    """Fake upstream; set ``.respond`` to a handler, read ``.urls`` after."""

    class Upstream:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def respond(self, request):
            return httpxyz.Response(200, content=BODY)

    fake = Upstream()
    real_client = httpxyz.Client

    def handler(request):
        fake.urls.append(str(request.url))
        return fake.respond(request)

    def client(**kwargs):
        return real_client(transport=httpxyz.MockTransport(handler), **kwargs)

    monkeypatch.setattr(study_service.httpxyz, "Client", client)
    return fake


@pytest.fixture()
def studies(session):
    """A study in Alpha (matches REGISTRY) and one in Other (does not)."""
    made = {}
    for name, identifier in (("Alpha", "a/b c"), ("Other", "p2")):
        project = make_project(session, name)
        patient = make_patient(session, project, identifier)
        study = make_study(session, patient, date(2020, 1, 2))
        made[name] = {"project": project.ProjectID, "study": study.StudyID}
    session.commit()
    return made


def test_the_default_config_has_no_sources():
    assert load_data_sources(DATA_SOURCES_PATH) == ()


def test_a_matching_study_lists_and_proxies_the_source(client, sources, upstream, studies):
    study_id = studies["Alpha"]["study"]

    listed = client.get(f"/studies/{study_id}/data-sources")
    fetched = client.get(f"/studies/{study_id}/data-sources/Registry")

    assert listed.json() == [{"name": "Registry", "collapse": True}]
    assert fetched.status_code == 200
    assert fetched.content == BODY
    assert fetched.headers["content-type"] == "application/json"
    # The identifier "a/b c" cannot add a path segment.
    assert upstream.urls == [
        "http://upstream:5000/api/project/Alpha/patient/a%2Fb%20c/study/2020-01-02"
    ]


def test_a_non_matching_project_gets_no_source(client, sources, upstream, studies):
    study_id = studies["Other"]["study"]

    assert client.get(f"/studies/{study_id}/data-sources").json() == []
    assert client.get(f"/studies/{study_id}/data-sources/Registry").status_code == 404
    assert upstream.urls == []


def test_an_invisible_study_is_404_and_never_reaches_upstream(
    client_scoped, sources, upstream, studies
):
    client, set_scope = client_scoped
    set_scope(scope_for(studies["Other"]["project"]))
    study_id = studies["Alpha"]["study"]

    assert client.get(f"/studies/{study_id}/data-sources").status_code == 404
    assert client.get(f"/studies/{study_id}/data-sources/Registry").status_code == 404
    assert upstream.urls == []


def test_a_project_member_can_fetch(client_scoped, sources, upstream, studies):
    client, set_scope = client_scoped
    set_scope(scope_for(studies["Alpha"]["project"]))

    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")

    assert response.status_code == 200
    assert response.content == BODY


def test_an_unknown_source_is_404(client, sources, upstream, studies):
    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Nope")

    assert response.status_code == 404
    assert upstream.urls == []


@pytest.mark.parametrize(
    ("respond", "status"),
    [
        (lambda request: httpxyz.Response(404), 404),
        (lambda request: httpxyz.Response(500), 502),
        (lambda request: (_ for _ in ()).throw(httpxyz.ReadTimeout("slow")), 502),
        (lambda request: (_ for _ in ()).throw(httpxyz.ConnectError("down")), 502),
    ],
    ids=["upstream-404", "upstream-500", "timeout", "unreachable"],
)
def test_upstream_failures_map_to_status(client, sources, upstream, studies, respond, status):
    upstream.respond = respond

    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")

    assert response.status_code == status
    assert "a/b c" not in response.text


def test_a_site_config_parses(tmp_path):
    path = tmp_path / "data_sources.yaml"
    path.write_text(
        "sources:\n"
        "  - name: Registry\n"
        "    url: http://h/{project}/{patient}/{date}\n"
        "    projects: [Alpha, Beta]\n"
    )

    assert load_data_sources(path) == (
        DataSource(name="Registry", url="http://h/{project}/{patient}/{date}", projects=["Alpha", "Beta"]),
    )
