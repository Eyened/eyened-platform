"""Study extensions: protocol callbacks after the study is in scope."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date

import pytest

import server.services.study_service as study_service
from eyened_orm.utils.factories import make_patient, make_project, make_study, scope_for
from server.study_extension import (
    EXTENSIONS_DIR,
    ExtensionContext,
    TablesContribution,
    get_extensions,
    load_extensions,
)

BODY = TablesContribution(groups={"table": [["a", 1]]})


@dataclass
class Registry:
    name: str = "Registry"
    projects: tuple[str, ...] = ("Alpha",)
    result: TablesContribution | None = field(default_factory=lambda: BODY)
    error: BaseException | None = None
    sleep_s: float = 0
    fetch_calls: int = 0
    last_ctx: ExtensionContext | None = None

    def applies(self, ctx: ExtensionContext) -> bool:
        return ctx.project_name in self.projects

    def fetch(self, ctx: ExtensionContext) -> TablesContribution | None:
        self.fetch_calls += 1
        self.last_ctx = ctx
        if self.sleep_s:
            time.sleep(self.sleep_s)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture()
def registry() -> Registry:
    return Registry()


@pytest.fixture()
def sources(registry: Registry, monkeypatch):
    monkeypatch.setattr(study_service, "get_extensions", lambda: (registry,))


@pytest.fixture()
def studies(session):
    made = {}
    for name, identifier in (("Alpha", "a/b c"), ("Other", "p2")):
        project = make_project(session, name)
        patient = make_patient(session, project, identifier)
        study = make_study(session, patient, date(2020, 1, 2))
        made[name] = {"project": project.ProjectID, "study": study.StudyID}
    session.commit()
    return made


def test_the_default_dir_has_no_extensions():
    get_extensions.cache_clear()
    assert load_extensions(EXTENSIONS_DIR) == ()


def test_a_matching_study_lists_and_fetches(client, sources, registry, studies):
    study_id = studies["Alpha"]["study"]

    listed = client.get(f"/studies/{study_id}/data-sources")
    fetched = client.get(f"/studies/{study_id}/data-sources/Registry")

    assert listed.json() == [{"name": "Registry"}]
    assert fetched.status_code == 200
    assert fetched.json() == {"kind": "tables", "groups": {"table": [["a", 1]]}}
    assert registry.fetch_calls == 1
    assert registry.last_ctx is not None
    assert registry.last_ctx.patient_identifier == "a/b c"
    assert registry.last_ctx.project_name == "Alpha"
    assert registry.last_ctx.study_date == date(2020, 1, 2)
    assert registry.last_ctx.session is not None


def test_a_non_matching_project_gets_no_source(client, sources, registry, studies):
    study_id = studies["Other"]["study"]

    assert client.get(f"/studies/{study_id}/data-sources").json() == []
    assert client.get(f"/studies/{study_id}/data-sources/Registry").status_code == 404
    assert registry.fetch_calls == 0


def test_an_invisible_study_is_404_and_never_calls_the_extension(
    client_scoped, sources, registry, studies
):
    client, set_scope = client_scoped
    set_scope(scope_for(studies["Other"]["project"]))
    study_id = studies["Alpha"]["study"]

    assert client.get(f"/studies/{study_id}/data-sources").status_code == 404
    assert client.get(f"/studies/{study_id}/data-sources/Registry").status_code == 404
    assert registry.fetch_calls == 0


def test_a_project_member_can_fetch(client_scoped, sources, studies):
    client, set_scope = client_scoped
    set_scope(scope_for(studies["Alpha"]["project"]))

    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")

    assert response.status_code == 200
    assert response.json()["kind"] == "tables"


def test_an_unknown_source_is_404(client, sources, registry, studies):
    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Nope")

    assert response.status_code == 404
    assert registry.fetch_calls == 0


def test_fetch_none_is_404(client, sources, registry, studies):
    registry.result = None

    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")

    assert response.status_code == 404
    assert "a/b c" not in response.text


def test_a_raised_fetch_is_502(client, sources, registry, studies):
    registry.error = RuntimeError("boom")

    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")

    assert response.status_code == 502
    assert "a/b c" not in response.text


def test_invalid_envelope_is_502(client, sources, registry, studies):
    registry.result = {"kind": "nope"}  # type: ignore[assignment]

    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")

    assert response.status_code == 502
    assert "a/b c" not in response.text


def test_a_slow_fetch_is_502(client, sources, registry, studies, monkeypatch):
    monkeypatch.setattr(study_service, "FETCH_TIMEOUT", 0.05)
    registry.sleep_s = 0.4

    started = time.perf_counter()
    response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources/Registry")
    elapsed = time.perf_counter() - started

    assert response.status_code == 502
    assert elapsed < 0.25
    assert "a/b c" not in response.text


def test_one_broken_applies_still_lists_the_other(client, monkeypatch, studies, caplog):
    @dataclass
    class Boom:
        name: str = "Boom"

        def applies(self, ctx: ExtensionContext) -> bool:
            raise RuntimeError(ctx.patient_identifier)

        def fetch(self, ctx: ExtensionContext) -> TablesContribution | None:
            return None

    good = Registry()
    monkeypatch.setattr(study_service, "get_extensions", lambda: (Boom(), good))

    with caplog.at_level("WARNING"):
        response = client.get(f"/studies/{studies['Alpha']['study']}/data-sources")

    assert response.status_code == 200
    assert response.json() == [{"name": "Registry"}]
    assert "Boom" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "a/b c" not in caplog.text
