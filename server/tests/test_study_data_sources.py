"""External data sources: proxied through the API, scoped by the study's project.

The upstream is never reachable from the browser, so these routes are the only
access path; a study the actor cannot see must not reach the upstream at all.
"""
from __future__ import annotations

from datetime import date

import anyio
import httpxyz
import pytest

from eyened_orm import Study

import server.config as config
import server.services.data_source_client as data_source_client
from eyened_orm.utils.factories import make_patient, make_project, make_study, scope_for
from server.dtos.dto_converter import DTOConverter
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
    monkeypatch.setattr(config, "get_data_sources", lambda: (REGISTRY,))


@pytest.fixture()
def upstream():
    """Fake upstream; set ``.respond`` to a handler, read ``.urls`` after.

    ``.respond`` may be sync or async; MockTransport awaits either.
    """
    from server.main import app_api

    class Upstream:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def respond(self, request):
            return httpxyz.Response(200, content=BODY)

    fake = Upstream()

    def handler(request):
        fake.urls.append(str(request.url))
        return fake.respond(request)

    mock = httpxyz.AsyncClient(transport=httpxyz.MockTransport(handler))
    app_api.dependency_overrides[data_source_client.get_data_source_client] = lambda: mock
    yield fake
    app_api.dependency_overrides.pop(data_source_client.get_data_source_client, None)


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


def test_a_study_in_a_configured_project_lists_its_sources(session, sources, studies):
    study = session.get(Study, studies["Alpha"]["study"])

    dto = DTOConverter.study_to_get(study)

    assert [d.model_dump() for d in dto.data_sources] == [{"name": "Registry", "collapse": True}]


def test_a_study_in_another_project_lists_no_sources(session, sources, studies):
    study = session.get(Study, studies["Other"]["study"])

    assert DTOConverter.study_to_get(study).data_sources == []


def test_a_matching_study_proxies_the_source(client, sources, upstream, studies):
    study_id = studies["Alpha"]["study"]

    fetched = client.get(f"/studies/{study_id}/data-sources/Registry")

    assert fetched.status_code == 200
    assert fetched.json() == {"table": [["a", 1]]}
    assert fetched.headers["content-type"] == "application/json"
    # The identifier "a/b c" cannot add a path segment.
    assert upstream.urls == [
        "http://upstream:5000/api/project/Alpha/patient/a%2Fb%20c/study/2020-01-02"
    ]


def test_a_non_matching_project_gets_no_source(client, sources, upstream, studies):
    study_id = studies["Other"]["study"]

    assert client.get(f"/studies/{study_id}/data-sources/Registry").status_code == 404
    assert upstream.urls == []


def test_an_invisible_study_is_404_and_never_reaches_upstream(
    client_scoped, sources, upstream, studies
):
    client, set_scope = client_scoped
    set_scope(scope_for(studies["Other"]["project"]))
    study_id = studies["Alpha"]["study"]

    assert client.get(f"/studies/{study_id}/data-sources/Registry").status_code == 404
    assert upstream.urls == []


def test_a_project_member_can_fetch(client_scoped, sources, upstream, studies):
    client, set_scope = client_scoped
    set_scope(scope_for(studies["Alpha"]["project"]))

    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")

    assert response.status_code == 200
    assert response.json() == {"table": [["a", 1]]}


def test_an_unknown_source_is_404(client, sources, upstream, studies):
    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Nope")

    assert response.status_code == 404
    assert upstream.urls == []


@pytest.mark.parametrize("identifier", ["", ".", ".."], ids=["empty", "dot", "dotdot"])
def test_a_path_changing_identifier_is_404_and_never_reaches_upstream(
    client, session, sources, upstream, identifier
):
    project = make_project(session, "Alpha")
    study = make_study(session, make_patient(session, project, identifier), date(2020, 1, 2))
    session.commit()

    response = client.get(f"/studies/{study.StudyID}/data-sources/Registry")

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


def test_named_tables_pass_through_unchanged(client, sources, upstream, studies):
    tables = {"Blood pressure": [[120, 80, "2019-03-01"], [118.5, None, "x"]], "Empty": []}
    upstream.respond = lambda request: httpxyz.Response(200, json=tables)

    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")

    assert response.status_code == 200
    assert response.json() == tables


@pytest.mark.parametrize(
    "body",
    [b"<html>login</html>", b'[["a", 1]]', b'{"table": ["not a row"]}'],
    ids=["html", "list", "row-not-a-list"],
)
def test_a_body_that_is_not_named_tables_is_502(
    client, sources, upstream, studies, caplog, body
):
    upstream.respond = lambda request: httpxyz.Response(200, content=body)

    with caplog.at_level("WARNING"):
        response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")

    assert response.status_code == 502
    assert "Data source Registry returned data that is not named tables" in caplog.text
    assert "a/b c" not in caplog.text
    assert "a%2Fb%20c" not in caplog.text
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


def test_the_upstream_call_holds_no_db_transaction(client, session, sources, upstream, studies):
    # `session` is the same object get_db yields to the request.
    seen = []

    def respond(request):
        seen.append(session.in_transaction())
        return httpxyz.Response(200, content=BODY)

    upstream.respond = respond

    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")

    assert response.status_code == 200
    assert seen == [False]


def test_an_upstream_that_never_answers_is_502(client, monkeypatch, sources, upstream, studies):
    monkeypatch.setattr(data_source_client, "DATA_SOURCE_TIMEOUT", 0.05)

    async def respond(request):
        await anyio.sleep(5)
        return httpxyz.Response(200, content=BODY)

    upstream.respond = respond

    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")

    assert response.status_code == 502
