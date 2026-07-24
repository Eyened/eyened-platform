# Search Module Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 1257-line `server/routes/search.py` into a Repository + Service + thin route, behind a test safety net that pins today's behavior, giving RBAC Step 2 a single seam for a project-visibility filter.

**Architecture:** Two PRs, split at the test/production-code line. PR 1 adds a reusable test-data factory and route-level characterization tests against today's endpoints, touching no production code. PR 2 extracts `SearchRepository` (pure query construction, in `orm/`) and a `server/services/search/` package (vocabulary, DSL translation, orchestration, RBAC seam), reduces `routes/search.py` to thin handlers, and folds in a short list of small fixes. SQL query shape is unchanged throughout; every response stays byte-identical.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (ORM `select()`), Pydantic v2, pytest 8, in-memory SQLite via `eyened_orm.utils.sqlite_testdb`, `fastapi.testclient.TestClient` (httpx).

## Global Constraints

- **No SQL rewrites.** The attribute-def N+1, the `OR`-of-joins `EXISTS`, and the redundant `DISTINCT` move **verbatim** into `SearchRepository`. They are follow-up work; a "while I'm here" fix breaks the behavior-preservation claim this plan exists to make auditable.
- **No RBAC.** `SearchService` gets a documented seam and an inert pass-through only.
- **No frontend changes.** Response DTO shapes are byte-identical; `response_model` and `DTOConverter` calls are unchanged.
- **Layering (enforced, not aspirational):** `orm/` must never import from `server/` — it is a separate distribution (`orm/setup.py`) and has **zero** such imports today. `server/services/` must never import from `server/routes/` — there are zero such imports today, and `server/services/acting_user.py` exists specifically to preserve that. Both directions are load-bearing for this plan's file layout.
- **Test style:** no mocking library. Function-scoped in-memory SQLite `session` fixture. One-line docstring per test. No thin-passthrough tests.
- **Naming:** every service stays findable as `services/**/*_service.py`.
- **Run tests with** `dev/.venv/bin/python -m pytest` (no `python`/`pytest` on `PATH`).
- **Commit after every task.** Never mix a behavior change into a move commit.

---

## Spec corrections (verified before planning)

The spec (`docs/superpowers/specs/2026-07-13-search-refactor-design.md`) was checked against the code at `feature/rbac-step1-service-layer`. Five claims did not survive. Each correction below is backed by a command that was actually run.

**1. Fix #3 (`SignatureField.nullable`/`multi`) is stale — dropped from this plan.**
The spec says both are "passed at construction but not declared on the model, so Pydantic v2's default `extra='ignore'` silently drops them." They **are** declared (`server/routes/search.py:660,663`), added by commit `aa817d5` (2026-06-24), *before* the spec was written. They are serialized today (verified: `Patient Identifier` → `multi: true`, `Laterality` → `nullable: true`), the client consumes both (`client/src/lib/browser/AdvancedFilters.svelte:117,129`, `client/src/lib/browser/browserContext.svelte.ts:139,151`), and both appear in `client/src/types/openapi.ts:2084,2089`. **No code change.** The follow-up "SignatureField frontend verification" is likewise closed.
*Consequence:* this was the spec's only intentional output change. The Behavior-Preservation Contract is now absolute — PR 2 changes **zero** bytes of output, which is a strictly stronger claim than the spec made.

**2. Fix #1 extends to two more dead symbols.** `create_condition` and `format_attr_condition` are confirmed callerless. So are `parse_attribute_var` and `ATTRIBUTE_VAR_RE` (`search.py:227-236`) — nothing calls them.

**3. The spec's `model[attr]` narrative is wrong.** Error Handling describes "the dynamic `model[attr]` syntax." No such syntax is live: `AttributeCondition` (`search.py:673-679`) carries `model`, `variable`, and `feature` as **separate structured fields**, and `_build_instance_select` reads them with `c.get("model")` / `c.get("variable")` / `c.get("feature")`. The `model[attr]` parser is the dead `parse_attribute_var`. The spec's *conclusion* still holds — `AttributeCondition.variable` is an unvalidated `str` — only the mechanism was misdescribed.

**4. The spec's file layout is circular — corrected in File Structure below.**
The spec puts `conditions.py` (with `format_condition`) in `server/services/search/`, while `SearchRepository` in `orm/` owns the `exists_*` builders. But those builders **call** `format_condition` (via `and_expr`, `search.py:365`), and `orm/` cannot import from `server/`. Likewise `exists_attributes_for_instance` needs `get_value_column_for_attribute` and `convert_search_value_to_attribute_type`, which need an `AttributeDefinition` **loaded from the DB** — so they cannot live above the repository either.
*Correction:* all SQLAlchemy-expression construction and attribute value coercion move into `orm/` alongside the repository. `server/services/search/conditions.py` keeps a real, DB-free, HTTP-free job: translating the request DSL into resolved condition objects. The spec's intent (UI vocabulary never crosses into `orm/`) is preserved exactly — `fields.py` stays in `server/services/search/`.

**5. `SearchService` cannot take the route's Pydantic `SearchQuery`.** The spec writes `search_instances(session, query)`. `SearchQuery` lives in `routes/search.py`; importing it into `services/` is the exact inversion `ActingUser` was written to prevent. *Correction:* the service takes explicit keyword arguments, and the route calls `service.search_instances(db, **query.model_dump())` — which unpacks to precisely those keywords. Same intent, legal arrow. `SignatureField` moves **into** `services/search/fields.py` (it is the vocabulary described to the client) and the route imports it downward for its `response_model`.

### Verified facts this plan depends on

Established by running code, not by reading it:

- `TestClient(app_api)` + `dependency_overrides` works. `server.main` imports cleanly under test; `app_api` is a sub-app mounted at `/api`, so tests POST to `/instances/search` (no prefix) and skip `app`'s lifespan and Redis entirely.
- **httpx was missing** and is required by `TestClient`. Added to `server/test-requirements.txt` (`httpx==0.28.*`). There is **no `TestClient` usage anywhere in the repo today** — PR 1 builds this harness from scratch. The spec treats route-level tests as free; they are not.
- `DTOConverter.image_instance_to_get` **raises** `ValueError("ImageInstance has no primary storage")` (`dto_converter.py:216-218`) unless the instance has an `ImageStorage` with `IsPrimary=True` plus a `StorageBackend`. The factory **must** create these or every characterization test 500s. The spec does not mention it.
- `ImageInstance.DatasetIdentifier` is **NOT NULL** despite emitting a `DeprecationWarning`. The factory must set it.
- `AttributesModel` is joined-table inheritance under `Model` (`segmentation.py:740`); `Model.Version` is NOT NULL. `make_attributes_model` must pass `Version`.
- `AttributeDefinition.AttributeName` carries a `UniqueConstraint`, so the attribute lookup's `scalar_one_or_none()` cannot raise `MultipleResultsFound`. No 500 risk there.
- **Unknown *static* field → 422.** Spec claim confirmed by request. Both asserts are unreachable.
- **Unknown *attribute* field → silently skipped, confirmed by request.** See Task 12.
- **Pre-existing bug, not in the spec:** `/studies/search/signature` advertises `"Study Instance UID"` (`search.py:1253`), but `study_searchable_fields` omits it — searching the field the server just advertised returns **422**. Pinned as-is in Task 5; **not fixed by this plan** — the fix needs a product call (add the field, or stop advertising it), so it is listed under Follow-up work.

### The silent-skip decision (spec's one open question)

The spec asks: "Confirm during planning whether that silent-skip is load-bearing for the frontend."

**Confirmed by experiment.** POSTing an attribute condition for a nonexistent attribute returns the **entire unfiltered result set** (`result_ids: ['img-a']`, `count: 1` against a 1-row dataset) — HTTP 200, no error. `exists_attributes_for_instance` resolves each definition and `continue`s past misses (`search.py:576-578`, `584-585`), so the predicate is dropped and the `AND` narrows nothing.

**It is not load-bearing.** The client only offers attributes enumerated by `/instances/search/signature`, which lists real `AttributeDefinition` rows, so a normally-behaving client never sends an unresolvable attribute. The skip is reachable only via stale client state (attribute renamed/deleted between signature fetch and search) or hand-rolled API calls.

**Recommendation: switch to `BadRequestError` (400).** A dropped filter is not a no-op — it is an inversion. The user asks "images where Quality == 5" and silently receives *every image*. That is the worst failure mode a filter has, and it is exactly the shape of a data-exposure bug once RBAC Step 2 lands on this surface. The spec's own Error Handling section reaches the same conclusion given this finding.

**Sequenced to protect the audit trail.** Tasks 6-11 do the extraction preserving silent-skip *exactly*, so PR 2's core lands as a pure structural move. Task 12 then flips it in its own commit, touching one behavior and one test. A reviewer sees the move and the change as separate diffs rather than having to disentangle them. **If you would rather keep silent-skip, drop Task 12 — nothing else in the plan depends on it.**

---

## File Structure

```
orm/eyened_orm/utils/
    factories.py                      # NEW (PR 1). Composable model builders +
                                      # seed_search_dataset(). Lives beside
                                      # sqlite_testdb.py, the established precedent for a
                                      # test utility shipped inside the orm package and
                                      # imported by BOTH orm and server tests.

orm/eyened_orm/repositories/search/   # NEW (PR 2). A package, for the same reason
                                      # services/search is one -- see below.
    __init__.py                       # Public surface via __all__: SearchRepository,
                                      # ResolvedCondition, AttributeConditionSpec, and the
                                      # entity aliases. The exists_*/select builders are
                                      # internal by omission -- nothing outside this package
                                      # should ever import them.
    aliases.py                        # ActiveSegmentation/ActiveFormAnnotation/SegCreator/
                                      # FormCreator/SegTag/FormTag/InstTag/StudyTag (~25 lines).
                                      # Pure ORM constructs; server/services/search/fields.py
                                      # imports them from here (server -> orm is legal).
    conditions.py                     # ResolvedCondition, AttributeConditionSpec,
                                      # format_condition, and_expr, entity_of,
                                      # partition_conditions_by_entity, attribute value
                                      # coercion (~150 lines).
    exists.py                         # The six exists_* semijoin builders (~280 lines).
                                      # Carries the attribute-def N+1 and the OR-EXISTS verbatim.
    selects.py                        # _build_instance_select / _build_study_select +
                                      # the selectinload option-sets (~200 lines).
    repository.py                     # SearchRepository: the five public methods (~90 lines).
                                      # Framework-agnostic SQLAlchemy; Session-as-argument.
                                      # Returns rows/counts.

server/services/search/               # NEW (PR 2). A package: search is the one non-CRUD service.
    __init__.py                       # Explicit public surface via __all__:
                                      #   SearchService, get_search_service, SignatureField,
                                      #   searchable_fields, study_searchable_fields,
                                      #   instance_order_by_fields, study_order_by_fields, operators
                                      # conditions.py is internal by omission.
    fields.py                         # UI-label -> ORM-attribute registry, the searchable_fields
                                      # Literals, order-by maps, SignatureField. The vocabulary.
    conditions.py                     # Request DSL -> ResolvedCondition/AttributeConditionSpec.
                                      # No DB, no HTTP, no SQLAlchemy expression building.
    search_service.py                 # SearchService: orchestration. THE RBAC SEAM.

server/routes/
    search.py                         # Thin handlers + HTTP contracts (SearchQuery,
                                      # SearchResponse, ...). Stays a flat module, like the
                                      # other 15 route files. Import path never moves,
                                      # so main.py needs no change and no shim is required.

server/tests/
    conftest.py                       # MODIFY (PR 1): add the `client` fixture.
    test_routes_search_instances.py   # NEW (PR 1)
    test_routes_search_studies.py     # NEW (PR 1)
    test_routes_search_signature.py   # NEW (PR 1)
    test_search_service.py            # NEW (PR 2)

orm/eyened_orm/tests/
    test_search_repository.py         # NEW (PR 2)

server/test-requirements.txt          # MODIFY (PR 1): httpx (DONE — already applied).
```

**Why the vocabulary lives in `services/`, not `routes/`:** `fields.py` has consumers in two layers — the route's Pydantic models type `variable` with the `searchable_fields` Literal, and `SearchService` resolves labels against the same maps. A symbol consumed by two layers must live in the lower one, or the upper layer becomes a dependency of the lower one.

**Why `orm/` owns expression building:** see Spec correction #4. `orm/` cannot import `server/`, and the `exists_*` builders call `format_condition`.

**Why the repository is a package, when the spec said one module** (`search_repository.py`). Measured, not guessed: the code being moved is **614 lines** before the `ResolvedCondition` rewrite — `exists_*` builders 278, `_build_instance_select` 105, attribute coercion 70, `_build_study_select` 48, the option-sets 47, the rest 66. Plus the public methods and dataclasses, one module lands around **700 lines**. For calibration, the largest existing repository is `task_repository.py` at **179** lines, the median is ~52, and *every* repository in the package combined is **770**. A single 700-line `search_repository.py` would be a kitchen-sink file roughly equal to the entire existing repositories layer, and would sit four-fold above the largest thing it is meant to look like.

This is the spec's own argument, applied where it bites harder. The spec justified `services/search/` being a package because "search is a genuine sub-domain, which is the bar for adding depth… it is the only service carrying a vocabulary and a DSL, which is why it brings three modules where the others bring one." The same is true one layer down, and the size disparity is starker: search is the only repository carrying an expression compiler and six semijoin builders. The package also buys the same thing it buys upstairs — an explicit public surface. Nothing outside should import `exists_forms_for_instance`; `__all__` says so, whereas a flat `search_repository.py` (or three flat `search_*.py` peers) leaves every internal equally importable.

`SearchRepository` stays in `repository.py` inside the package rather than a redundant `search_repository.py`; the package name already carries "search", and `repositories/search/repository.py` reads better than `repositories/search/search_repository.py`. It remains findable, since the import path (`eyened_orm.repositories.search`) is what callers actually use.

**On imports:** the `python-project-structure` skill prefers absolute imports throughout. This plan follows the **codebase** instead, which uses absolute imports for `eyened_orm` and relative ones within `server` (`study_service.py` does both: `from eyened_orm.repositories.study_repository import StudyRepository` alongside `from .acting_user import ActingUser`). Consistency with the surrounding code wins here; a lone absolute-import module would just look like a mistake.

---

# PR 1 — Safety net

Touches **no production code**. Every test here must stay green through PR 2 (with one deliberate, isolated exception in Task 12).

### Task 1: TestClient harness

The repo has no `TestClient` anywhere. This task builds the harness and proves it works on one trivial search before any characterization test depends on it.

**Files:**
- Modify: `server/test-requirements.txt` (**already applied** — verify only)
- Modify: `server/tests/conftest.py`
- Test: `server/tests/test_routes_search_instances.py`

**Interfaces:**
- Produces: a `client` pytest fixture — `TestClient` bound to `app_api` with `get_db` overridden to yield the test `session` and `get_current_user` overridden to a static `CurrentUser`. Tasks 3-5 and Task 12 consume it.

- [ ] **Step 1: Verify httpx is declared and installed**

`server/test-requirements.txt` should already read:

```
-r requirements.txt
pytest==8.*
# Required by fastapi.testclient.TestClient (route-level tests).
httpx==0.28.*
```

Run: `dev/.venv/bin/python -c "import httpx; print(httpx.__version__)"`
Expected: `0.28.1` (if it errors, run `dev/.venv/bin/pip install 'httpx==0.28.*'`)

- [ ] **Step 2: Add the `client` fixture to `server/tests/conftest.py`**

Append to the existing file (keep the existing imports and `pytest_configure` exactly as they are — the env vars it sets must be in place before `server.main` is imported):

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(session):
    """TestClient bound to app_api, with the DB and auth dependencies overridden.

    app_api is the sub-app mounted at /api in server.main, so paths here carry no
    /api prefix. Binding to it (rather than to `app`) also skips the lifespan and
    the Redis connection, which tests neither have nor need.
    """
    # Imported lazily: pytest_configure above must set the DB env vars first.
    from server.db import get_db
    from server.main import app_api
    from server.routes.auth import CurrentUser, get_current_user

    def _get_db():
        yield session

    # A CurrentUser with no backing Creator row: search never calls get_creator(),
    # and seeding one would pollute /instances/search/signature's creator list.
    app_api.dependency_overrides[get_db] = _get_db
    app_api.dependency_overrides[get_current_user] = lambda: CurrentUser(
        creator_id=1, username="tester", role="admin"
    )
    with TestClient(app_api) as c:
        yield c
    app_api.dependency_overrides.clear()
```

- [ ] **Step 3: Write a failing smoke test**

Create `server/tests/test_routes_search_instances.py`:

```python
from datetime import date, datetime

from eyened_orm import (
    DeviceInstance,
    DeviceModel,
    ImageInstance,
    ImageStorage,
    Patient,
    Project,
    Series,
    StorageBackend,
    Study,
)
from eyened_orm.project import ExternalEnum


def test_instance_search_returns_a_seeded_instance(client, session):
    """The harness reaches the real endpoint and renders one seeded instance."""
    backend = StorageBackend(Key="bk", Kind="local")
    session.add(backend)
    session.flush()
    project = Project(ProjectName="P", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier="ID", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=date(2024, 1, 1))
    session.add(study)
    session.flush()
    series = Series(StudyID=study.StudyID)
    session.add(series)
    session.flush()
    model = DeviceModel(Manufacturer="Mf", ManufacturerModelName="M")
    session.add(model)
    session.flush()
    device = DeviceInstance(DeviceModelID=model.DeviceModelID, Description="d")
    session.add(device)
    session.flush()
    image = ImageInstance(
        PublicID="img-a",
        SeriesID=series.SeriesID,
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier="ds-a",
        Rows_y=4,
        Columns_x=4,
        DateInserted=datetime(2024, 1, 1),
    )
    session.add(image)
    session.flush()
    session.add(
        ImageStorage(
            ImageInstanceID=image.ImageInstanceID,
            StorageBackendID=backend.StorageBackendID,
            ObjectKey="obj-a",
            Format="png",
            IsPrimary=True,
        )
    )
    session.commit()

    resp = client.post(
        "/instances/search",
        json={"conditions": [], "order_by": "Study Date", "order": "ASC", "include_count": True},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["result_ids"] == ["img-a"]
    assert body["count"] == 1
```

- [ ] **Step 4: Run it**

Run: `dev/.venv/bin/python -m pytest server/tests/test_routes_search_instances.py -q`
Expected: PASS (1 passed). This exact test has been run against this codebase and passes.

If it fails on `ImageInstance has no primary storage`, the `ImageStorage`/`IsPrimary=True` row is missing — that is the failure mode this step exists to catch early.

- [ ] **Step 5: Commit**

```bash
git add server/test-requirements.txt server/tests/conftest.py server/tests/test_routes_search_instances.py
git commit -m "test(search): add TestClient harness for route-level tests"
```

---

### Task 2: Search test-data factory

The spec's single largest piece of work. Composable builders serve the deferred "no Segmentation factory exists" findings from the Repository/Service spec; `seed_search_dataset` composes them into the one fixed graph the characterization tests snapshot.

**Files:**
- Create: `orm/eyened_orm/utils/factories.py`
- Test: `orm/eyened_orm/tests/test_factories.py`

**Interfaces:**
- Produces (consumed by Tasks 3-5, 8, 10, 12):
  - `make_storage_backend(session, key="test-backend") -> StorageBackend`
  - `make_creator(session, name, is_human=True) -> Creator`
  - `make_project(session, name) -> Project`
  - `make_patient(session, project, identifier, birth_date=None, sex=None) -> Patient`
  - `make_study(session, patient, study_date, description=None, study_round=None) -> Study`
  - `make_series(session, study) -> Series`
  - `make_device(session, key) -> DeviceInstance`
  - `make_image(session, series, device, backend, public_id, *, inactive=False, date_inserted=None, **cols) -> ImageInstance`
  - `make_feature(session, name) -> Feature`
  - `make_segmentation(session, image, feature, creator, *, inactive=False) -> Segmentation`
  - `make_form_schema(session, name) -> FormSchema`
  - `make_form_annotation(session, schema, patient, creator, *, study=None, image=None, inactive=False) -> FormAnnotation`
  - `make_tag(session, name, tag_type, creator) -> Tag`
  - `make_attribute(session, name, dtype) -> AttributeDefinition`
  - `make_attributes_model(session, name, outputs=(), version="1") -> AttributesModel`
  - `make_attribute_value(session, attr, *, image=None, model=None, value=None) -> AttributeValue`
  - `seed_search_dataset(session) -> SearchDataset`
  - `SearchDataset` dataclass: `.images: dict[str, ImageInstance]`, `.studies: dict[str, Study]`, `.projects: dict[str, Project]`

- [ ] **Step 1: Write the failing test**

Create `orm/eyened_orm/tests/test_factories.py`:

```python
from sqlalchemy import func, select

from eyened_orm import ImageInstance
from eyened_orm.utils.factories import seed_search_dataset


def test_seed_search_dataset_builds_the_documented_graph(session):
    """The fixed dataset seeds 4 instances across 2 projects, one of them inactive."""
    data = seed_search_dataset(session)

    assert set(data.images) == {"a1", "a2", "b1", "inactive"}
    assert set(data.projects) == {"alpha", "beta"}
    assert data.images["inactive"].Inactive is True
    assert session.scalar(select(func.count()).select_from(ImageInstance)) == 4


def test_seeded_images_are_renderable_by_the_dto_converter(session):
    """Every active instance has the primary storage DTOConverter requires."""
    data = seed_search_dataset(session)

    for key in ("a1", "a2", "b1"):
        assert data.images[key].primary_storage is not None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `dev/.venv/bin/python -m pytest orm/eyened_orm/tests/test_factories.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eyened_orm.utils.factories'`

- [ ] **Step 3: Write the factory**

Create `orm/eyened_orm/utils/factories.py`. This code has been executed against this schema and works:

```python
"""Composable model builders and a fixed dataset for search/annotation tests.

Lives beside ``sqlite_testdb`` so both ``orm`` and ``server`` test suites can
import it. Builders ``flush()`` (never ``commit()``) so callers control the
transaction; only ``seed_search_dataset`` commits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy.orm import Session

from eyened_orm import (
    Creator,
    DeviceInstance,
    DeviceModel,
    Feature,
    FormAnnotation,
    FormAnnotationTagLink,
    FormSchema,
    ImageInstance,
    ImageInstanceTagLink,
    ImageStorage,
    Patient,
    Project,
    Segmentation,
    SegmentationTagLink,
    Series,
    StorageBackend,
    Study,
    StudyTagLink,
    Tag,
)
from eyened_orm.attributes import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModel,
    AttributesModelOutput,
    AttributeValue,
)
from eyened_orm.patient import SexEnum
from eyened_orm.project import ExternalEnum
from eyened_orm.segmentation import DataRepresentation, Datatype
from eyened_orm.tag import TagType


def make_storage_backend(session: Session, key: str = "test-backend") -> StorageBackend:
    b = StorageBackend(Key=key, Kind="local")
    session.add(b)
    session.flush()
    return b


def make_creator(session: Session, name: str, is_human: bool = True) -> Creator:
    c = Creator(CreatorName=name, IsHuman=is_human)
    session.add(c)
    session.flush()
    return c


def make_project(session: Session, name: str) -> Project:
    p = Project(ProjectName=name, External=ExternalEnum.N)
    session.add(p)
    session.flush()
    return p


def make_patient(session, project, identifier, birth_date=None, sex=None) -> Patient:
    p = Patient(
        PatientIdentifier=identifier,
        ProjectID=project.ProjectID,
        BirthDate=birth_date,
        Sex=sex,
    )
    session.add(p)
    session.flush()
    return p


def make_study(session, patient, study_date, description=None, study_round=None) -> Study:
    s = Study(
        PatientID=patient.PatientID,
        StudyDate=study_date,
        StudyDescription=description,
        StudyRound=study_round,
    )
    session.add(s)
    session.flush()
    return s


def make_series(session, study) -> Series:
    s = Series(StudyID=study.StudyID)
    session.add(s)
    session.flush()
    return s


def make_device(session, key: str) -> DeviceInstance:
    model = DeviceModel(Manufacturer=f"Mf-{key}", ManufacturerModelName=f"M-{key}")
    session.add(model)
    session.flush()
    d = DeviceInstance(DeviceModelID=model.DeviceModelID, Description=f"d-{key}")
    session.add(d)
    session.flush()
    return d


def make_image(
    session,
    series,
    device,
    backend,
    public_id: str,
    *,
    inactive: bool = False,
    date_inserted: datetime | None = None,
    **cols,
) -> ImageInstance:
    """Create an ImageInstance plus the primary ImageStorage the DTO layer requires.

    ``DTOConverter.image_instance_to_get`` raises without a primary storage, so
    the storage row is part of the instance's minimum viable shape, not an extra.
    ``DatasetIdentifier`` is deprecated but still NOT NULL, hence set here.
    """
    img = ImageInstance(
        PublicID=public_id,
        SeriesID=series.SeriesID,
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier=f"ds-{public_id}",
        Rows_y=4,
        Columns_x=4,
        Inactive=inactive,
        DateInserted=date_inserted or datetime(2024, 1, 1),
        **cols,
    )
    session.add(img)
    session.flush()
    session.add(
        ImageStorage(
            ImageInstanceID=img.ImageInstanceID,
            StorageBackendID=backend.StorageBackendID,
            ObjectKey=f"obj-{public_id}",
            Format="png",
            IsPrimary=True,
        )
    )
    session.flush()
    return img


def make_feature(session, name: str) -> Feature:
    f = Feature(FeatureName=name)
    session.add(f)
    session.flush()
    return f


def make_segmentation(session, image, feature, creator, *, inactive=False) -> Segmentation:
    seg = Segmentation(
        ImageInstanceID=image.ImageInstanceID,
        FeatureID=feature.FeatureID,
        CreatorID=creator.CreatorID,
        DataType=Datatype.R8UI,
        DataRepresentation=DataRepresentation.Binary,
        Depth=1,
        Height=4,
        Width=4,
        Inactive=inactive,
        DateInserted=datetime(2024, 1, 1),
    )
    session.add(seg)
    session.flush()
    return seg


def make_form_schema(session, name: str) -> FormSchema:
    s = FormSchema(SchemaName=name)
    session.add(s)
    session.flush()
    return s


def make_form_annotation(
    session, schema, patient, creator, *, study=None, image=None, inactive=False
) -> FormAnnotation:
    fa = FormAnnotation(
        FormSchemaID=schema.FormSchemaID,
        PatientID=patient.PatientID,
        CreatorID=creator.CreatorID,
        StudyID=study.StudyID if study is not None else None,
        ImageInstanceID=image.ImageInstanceID if image is not None else None,
        Inactive=inactive,
    )
    session.add(fa)
    session.flush()
    return fa


def make_tag(session, name: str, tag_type: TagType, creator) -> Tag:
    t = Tag(
        TagName=name,
        TagType=tag_type,
        TagDescription=f"desc-{name}",
        CreatorID=creator.CreatorID,
    )
    session.add(t)
    session.flush()
    return t


def make_attribute(session, name: str, dtype: AttributeDataType) -> AttributeDefinition:
    a = AttributeDefinition(AttributeName=name, AttributeDataType=dtype)
    session.add(a)
    session.flush()
    return a


def make_attributes_model(session, name: str, outputs=(), version: str = "1") -> AttributesModel:
    """Create an attributes Model. ``Version`` is NOT NULL on the joined-table parent."""
    m = AttributesModel(ModelName=name, Version=version)
    session.add(m)
    session.flush()
    for attr in outputs:
        session.add(AttributesModelOutput(ModelID=m.ModelID, AttributeID=attr.AttributeID))
    session.flush()
    return m


def make_attribute_value(session, attr, *, image=None, model=None, value=None) -> AttributeValue:
    kwargs = {"AttributeID": attr.AttributeID}
    if image is not None:
        kwargs["ImageInstanceID"] = image.ImageInstanceID
    if model is not None:
        kwargs["ModelID"] = model.ModelID
    if attr.AttributeDataType == AttributeDataType.Int:
        kwargs["ValueInt"] = value
    elif attr.AttributeDataType == AttributeDataType.Float:
        kwargs["ValueFloat"] = value
    else:
        kwargs["ValueText"] = value
    av = AttributeValue(**kwargs)
    session.add(av)
    session.flush()
    return av


@dataclass
class SearchDataset:
    """Handles into the fixed dataset seeded by ``seed_search_dataset``."""

    images: dict[str, ImageInstance] = field(default_factory=dict)
    studies: dict[str, Study] = field(default_factory=dict)
    projects: dict[str, Project] = field(default_factory=dict)


def seed_search_dataset(session: Session) -> SearchDataset:
    """Seed a fixed 2-project graph that lights up every exists_* branch.

    img-a1  project Alpha: segmentation (feat-x / seg-creator / seg-tag),
            image-level form annotation (schema-x / form-creator / form-tag),
            image tag, attribute Quality=5 produced by model M1.
    img-a2  project Alpha: plain, no annotations.
    img-b1  project Beta: plain; its study carries a study-tag and a
            study-level form annotation.
    img-inactive  project Alpha: Inactive=True, must never be returned.
    """
    backend = make_storage_backend(session)
    seg_creator = make_creator(session, "seg-creator")
    form_creator = make_creator(session, "form-creator")

    alpha = make_project(session, "Alpha")
    beta = make_project(session, "Beta")

    pat_a = make_patient(session, alpha, "PAT-A", date(1980, 1, 1), SexEnum.F)
    pat_b = make_patient(session, beta, "PAT-B", date(1990, 2, 2), SexEnum.M)

    study_a = make_study(session, pat_a, date(2024, 1, 1), "study-a", 1)
    study_b = make_study(session, pat_b, date(2024, 6, 1), "study-b", 2)

    ser_a = make_series(session, study_a)
    ser_b = make_series(session, study_b)
    dev = make_device(session, "d1")

    a1 = make_image(session, ser_a, dev, backend, "img-a1", date_inserted=datetime(2024, 1, 1))
    a2 = make_image(session, ser_a, dev, backend, "img-a2", date_inserted=datetime(2024, 1, 2))
    b1 = make_image(session, ser_b, dev, backend, "img-b1", date_inserted=datetime(2024, 6, 1))
    inactive = make_image(
        session, ser_a, dev, backend, "img-inactive",
        inactive=True, date_inserted=datetime(2024, 1, 3),
    )

    feat_x = make_feature(session, "feat-x")
    seg = make_segmentation(session, a1, feat_x, seg_creator)

    schema_x = make_form_schema(session, "schema-x")
    fa_img = make_form_annotation(session, schema_x, pat_a, form_creator, image=a1)
    make_form_annotation(session, schema_x, pat_b, form_creator, study=study_b)

    seg_tag = make_tag(session, "seg-tag", TagType.Segmentation, seg_creator)
    form_tag = make_tag(session, "form-tag", TagType.FormAnnotation, form_creator)
    img_tag = make_tag(session, "img-tag", TagType.ImageInstance, seg_creator)
    study_tag = make_tag(session, "study-tag", TagType.Study, seg_creator)

    session.add(SegmentationTagLink(
        SegmentationID=seg.SegmentationID, TagID=seg_tag.TagID, CreatorID=seg_creator.CreatorID))
    session.add(FormAnnotationTagLink(
        FormAnnotationID=fa_img.FormAnnotationID, TagID=form_tag.TagID, CreatorID=form_creator.CreatorID))
    session.add(ImageInstanceTagLink(
        ImageInstanceID=a1.ImageInstanceID, TagID=img_tag.TagID, CreatorID=seg_creator.CreatorID))
    session.add(StudyTagLink(
        StudyID=study_b.StudyID, TagID=study_tag.TagID, CreatorID=seg_creator.CreatorID))

    quality = make_attribute(session, "Quality", AttributeDataType.Int)
    m1 = make_attributes_model(session, "M1", outputs=[quality])
    make_attribute_value(session, quality, image=a1, model=m1, value=5)

    session.commit()
    return SearchDataset(
        images={"a1": a1, "a2": a2, "b1": b1, "inactive": inactive},
        studies={"a": study_a, "b": study_b},
        projects={"alpha": alpha, "beta": beta},
    )
```

- [ ] **Step 4: Run the tests**

Run: `dev/.venv/bin/python -m pytest orm/eyened_orm/tests/test_factories.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/utils/factories.py orm/eyened_orm/tests/test_factories.py
git commit -m "test(orm): add composable model factories and the fixed search dataset"
```

---

### Task 3: Characterization tests — instance search

Pins today's instance-search behavior: every condition type, every EXISTS branch, pagination, `include_count`, inactive exclusion, and the two dead-code claims the extraction relies on.

**Files:**
- Modify: `server/tests/test_routes_search_instances.py`

**Interfaces:**
- Consumes: the `client` fixture (Task 1); `seed_search_dataset` / `SearchDataset` (Task 2).

- [ ] **Step 1: Replace the smoke test with the characterization suite**

Rewrite `server/tests/test_routes_search_instances.py` entirely (the Task 1 smoke test was scaffolding; the factory now covers it):

```python
import pytest

from eyened_orm.utils.factories import seed_search_dataset


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


def _search(client, conditions, **kw):
    body = {"conditions": conditions, "order_by": "Date Inserted", "order": "ASC"}
    body.update(kw)
    resp = client.post("/instances/search", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _cond(variable, value, operator="=="):
    return {"type": "default", "variable": variable, "operator": operator, "value": value}


def test_unfiltered_search_returns_active_instances_only(client, data):
    """No conditions returns every active instance in Date Inserted order; inactive is excluded."""
    body = _search(client, [], include_count=True)

    assert body["result_ids"] == ["img-a1", "img-a2", "img-b1"]
    assert body["count"] == 3


def test_include_count_defaults_to_null(client, data):
    """count is omitted (None) unless include_count is requested."""
    body = _search(client, [])

    assert body.get("count") is None


@pytest.mark.parametrize(
    "variable,value,expected",
    [
        ("Project Name", "Alpha", ["img-a1", "img-a2"]),
        ("Patient Identifier", "PAT-B", ["img-b1"]),
        ("Segmentation Feature Name", "feat-x", ["img-a1"]),
        ("Segmentation Creator Name", "seg-creator", ["img-a1"]),
        ("Segmentation Tag Name", "seg-tag", ["img-a1"]),
        ("Form Schema Name", "schema-x", ["img-a1"]),
        ("Form Creator Name", "form-creator", ["img-a1"]),
        ("Form Tag Name", "form-tag", ["img-a1"]),
        ("Image Tag Name", "img-tag", ["img-a1"]),
    ],
)
def test_each_exists_branch_filters_to_the_expected_instances(
    client, data, variable, value, expected
):
    """Each searchable field routes through its EXISTS branch and matches the right rows."""
    assert _search(client, [_cond(variable, value)])["result_ids"] == expected


@pytest.mark.parametrize(
    "variable,value",
    [
        ("Project Name", "NoSuchProject"),
        ("Segmentation Feature Name", "no-such-feature"),
        ("Form Tag Name", "no-such-tag"),
        ("Image Tag Name", "no-such-tag"),
    ],
)
def test_each_exists_branch_has_an_empty_case(client, data, variable, value):
    """A non-matching value returns no rows rather than falling open."""
    body = _search(client, [_cond(variable, value)], include_count=True)

    assert body["result_ids"] == []
    assert body["has_more"] is False


def test_conditions_are_or_ed_together(client, data):
    """Multiple conditions OR globally (today's semantics), they do not AND."""
    body = _search(client, [_cond("Project Name", "Alpha"), _cond("Patient Identifier", "PAT-B")])

    assert body["result_ids"] == ["img-a1", "img-a2", "img-b1"]


def test_in_operator_matches_any_listed_value(client, data):
    """A list value becomes an IN over the mapped column."""
    body = _search(client, [_cond("Patient Identifier", ["PAT-A", "PAT-B"], operator="IN")])

    assert body["result_ids"] == ["img-a1", "img-a2", "img-b1"]


def test_attribute_condition_filters_by_model_produced_value(client, data):
    """An attribute condition resolves the definition and filters on the typed value column."""
    body = _search(
        client,
        [{"type": "attribute", "model": "M1", "variable": "Quality", "operator": "==", "value": 5}],
    )

    assert body["result_ids"] == ["img-a1"]


def test_order_desc_reverses_results(client, data):
    """order=DESC reverses the sort while keeping the ImageInstanceID tiebreaker."""
    body = _search(client, [], order="DESC")

    assert body["result_ids"] == ["img-b1", "img-a2", "img-a1"]


def test_pagination_reports_has_more_and_walks_pages(client, data):
    """limit+1 lookahead drives has_more; page N returns the Nth window."""
    page0 = _search(client, [], limit=2, page=0)
    page1 = _search(client, [], limit=2, page=1)

    assert page0["result_ids"] == ["img-a1", "img-a2"]
    assert page0["has_more"] is True
    assert page1["result_ids"] == ["img-b1"]
    assert page1["has_more"] is False


def test_studies_are_derived_from_instances_in_instance_order(client, data):
    """The studies block is the instances' distinct studies, in first-appearance order."""
    body = _search(client, [])

    assert [s["id"] for s in body["studies"]] == [
        data.studies["a"].StudyID,
        data.studies["b"].StudyID,
    ]


def test_empty_result_returns_the_empty_envelope(client, data):
    """A search matching nothing returns empty lists and has_more False, not a 404."""
    body = _search(client, [_cond("Project Name", "NoSuchProject")], include_count=True)

    assert body["instances"] == []
    assert body["studies"] == []
    assert body["result_ids"] == []
    assert body["has_more"] is False


def test_unknown_static_field_is_rejected_by_pydantic(client, data):
    """An unknown static field 422s at request parsing -- the reason both asserts are dead code."""
    resp = client.post(
        "/instances/search",
        json={
            "conditions": [_cond("Patient Identifir", "PAT-A")],
            "order_by": "Study Date",
            "order": "ASC",
        },
    )

    assert resp.status_code == 422


def test_unknown_order_by_is_rejected_by_pydantic(client, data):
    """order_by is Literal-typed, so an unknown sort field 422s rather than KeyError-ing."""
    resp = client.post(
        "/instances/search",
        json={"conditions": [], "order_by": "Nonsense", "order": "ASC"},
    )

    assert resp.status_code == 422
```

- [ ] **Step 2: Run them**

Run: `dev/.venv/bin/python -m pytest server/tests/test_routes_search_instances.py -q`
Expected: PASS. The dataset, every EXISTS branch, pagination and the 422s have all been verified against this codebase.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_routes_search_instances.py
git commit -m "test(search): characterize instance search behavior"
```

---

### Task 4: Characterization tests — study search

**Files:**
- Create: `server/tests/test_routes_search_studies.py`

**Interfaces:**
- Consumes: `client` (Task 1), `seed_search_dataset` (Task 2).

- [ ] **Step 1: Write the tests**

Create `server/tests/test_routes_search_studies.py`:

```python
import pytest

from eyened_orm.utils.factories import seed_search_dataset


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


def _search(client, conditions, **kw):
    body = {"conditions": conditions, "order_by": "Study Date", "order": "ASC"}
    body.update(kw)
    resp = client.post("/studies/search", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _cond(variable, value, operator="=="):
    return {"variable": variable, "operator": operator, "value": value}


def test_unfiltered_study_search_returns_all_studies(client, data):
    """No conditions returns every study in Study Date order."""
    body = _search(client, [], include_count=True)

    assert body["result_ids"] == [data.studies["a"].StudyID, data.studies["b"].StudyID]
    assert body["count"] == 2


@pytest.mark.parametrize(
    "variable,value,expected_key",
    [
        ("Project Name", "Beta", "b"),
        ("Patient Identifier", "PAT-A", "a"),
        ("Study Description", "study-a", "a"),
        ("Study Round", 2, "b"),
        ("Study Tag Name", "study-tag", "b"),
        ("Form Schema Name", "schema-x", "b"),
        ("Form Creator Name", "form-creator", "b"),
    ],
)
def test_each_study_branch_filters_to_the_expected_study(
    client, data, variable, value, expected_key
):
    """Each study-searchable field routes through its branch and matches the right study.

    Only the study-level form annotation (on study-b) satisfies the forms EXISTS,
    which correlates on StudyID; img-a1's form annotation is image-level.
    """
    body = _search(client, [_cond(variable, value)])

    assert body["result_ids"] == [data.studies[expected_key].StudyID]


def test_study_search_returns_instances_for_matched_studies(client, data):
    """The instances block carries every active instance of the matched studies."""
    body = _search(client, [_cond("Project Name", "Alpha")])

    assert sorted(i["id"] for i in body["instances"]) == ["img-a1", "img-a2"]


def test_study_search_pagination_reports_has_more(client, data):
    """limit+1 lookahead drives has_more on the study surface too."""
    page0 = _search(client, [], limit=1, page=0)
    page1 = _search(client, [], limit=1, page=1)

    assert page0["result_ids"] == [data.studies["a"].StudyID]
    assert page0["has_more"] is True
    assert page1["result_ids"] == [data.studies["b"].StudyID]
    assert page1["has_more"] is False


def test_study_search_empty_result_returns_the_empty_envelope(client, data):
    """A study search matching nothing returns empty lists, not a 404."""
    body = _search(client, [_cond("Project Name", "NoSuchProject")], include_count=True)

    assert body["studies"] == []
    assert body["instances"] == []
    assert body["result_ids"] == []
    assert body["has_more"] is False


def test_study_search_unknown_field_is_rejected_by_pydantic(client, data):
    """study_searchable_fields is a Literal, so an unknown field 422s at parsing."""
    resp = client.post(
        "/studies/search",
        json={
            "conditions": [_cond("Nonsense", "x")],
            "order_by": "Study Date",
            "order": "ASC",
        },
    )

    assert resp.status_code == 422
```

- [ ] **Step 2: Run them**

Run: `dev/.venv/bin/python -m pytest server/tests/test_routes_search_studies.py -q`
Expected: PASS

If `Study Round`/`Study Description` unexpectedly fail, check the seeded values in `seed_search_dataset` (`study-a`/round 1, `study-b`/round 2) before touching production code — the tests are the thing that is allowed to be wrong in PR 1, never `search.py`.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_routes_search_studies.py
git commit -m "test(search): characterize study search behavior"
```

---

### Task 5: Characterization tests — signature endpoints

Both signature endpoints enumerate cross-project names, which makes them an RBAC Step 2 leak surface in their own right. Pinning them now is what lets Step 2 prove it changed them deliberately.

**Files:**
- Create: `server/tests/test_routes_search_signature.py`

**Interfaces:**
- Consumes: `client` (Task 1), `seed_search_dataset` (Task 2).

- [ ] **Step 1: Write the tests**

Create `server/tests/test_routes_search_signature.py`:

```python
import pytest

from eyened_orm.utils.factories import seed_search_dataset


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


def _by_name(items):
    return {item["name"]: item for item in items}


def test_instance_signature_lists_every_searchable_field(client, data):
    """The instance signature advertises exactly the fields searchable_fields allows."""
    resp = client.get("/instances/search/signature")

    assert resp.status_code == 200
    assert set(_by_name(resp.json())) == {
        "Image DBID",
        "Laterality",
        "Modality",
        "ETDRS Field",
        "Color Fundus Quality",
        "Study Date",
        "Patient Identifier",
        "Patient Sex",
        "Patient Birthdate",
        "Project Name",
        "Device Model ID",
        "Segmentation Feature Name",
        "Segmentation Creator Name",
        "Segmentation Tag Name",
        "Form Schema Name",
        "Form Creator Name",
        "Form Tag Name",
        "Image Tag Name",
        "Quality",
    }


def test_instance_signature_exposes_nullable_and_multi(client, data):
    """nullable/multi are declared, serialized, and consumed by the client -- not dropped."""
    fields = _by_name(client.get("/instances/search/signature").json())

    assert fields["Patient Identifier"]["multi"] is True
    assert fields["Laterality"]["nullable"] is True


def test_instance_signature_enumerates_db_derived_values(client, data):
    """DB-derived fields carry the seeded values, sorted."""
    fields = _by_name(client.get("/instances/search/signature").json())

    assert fields["Project Name"]["values"] == ["Alpha", "Beta"]
    assert fields["Segmentation Feature Name"]["values"] == ["feat-x"]
    assert fields["Segmentation Tag Name"]["values"] == ["seg-tag"]
    assert fields["Form Tag Name"]["values"] == ["form-tag"]
    assert fields["Image Tag Name"]["values"] == ["img-tag"]


def test_instance_signature_describes_attributes(client, data):
    """Attribute definitions surface as type=attribute entries carrying their model."""
    quality = _by_name(client.get("/instances/search/signature").json())["Quality"]

    assert quality["type"] == "attribute"
    assert quality["values"] == "int"
    assert quality["model"] == "M1"


def test_study_signature_enumerates_db_derived_values(client, data):
    """The study signature carries the seeded project/schema/tag values."""
    fields = _by_name(client.get("/studies/search/signature").json())

    assert fields["Project Name"]["values"] == ["Alpha", "Beta"]
    assert fields["Form Schema Name"]["values"] == ["schema-x"]
    assert fields["Study Tag Name"]["values"] == ["study-tag"]


def test_study_signature_advertises_a_field_that_cannot_be_searched(client, data):
    """PRE-EXISTING BUG pinned as-is: the signature offers 'Study Instance UID',
    but study_searchable_fields omits it, so searching it 422s. Not fixed by this
    plan -- see Follow-up work; this test documents the bug until someone does."""
    fields = _by_name(client.get("/studies/search/signature").json())
    assert "Study Instance UID" in fields

    resp = client.post(
        "/studies/search",
        json={
            "conditions": [
                {"variable": "Study Instance UID", "operator": "==", "value": "x"}
            ],
            "order_by": "Study Date",
            "order": "ASC",
        },
    )

    assert resp.status_code == 422
```

- [ ] **Step 2: Run them**

Run: `dev/.venv/bin/python -m pytest server/tests/test_routes_search_signature.py -q`
Expected: PASS. The `Study Instance UID` mismatch and the `nullable`/`multi` values were verified by request against this codebase.

- [ ] **Step 3: Run the whole suite — this is the PR 1 gate**

Run: `dev/.venv/bin/python -m pytest -q`
Expected: PASS, with all pre-existing tests (276 as of 2026-07-16) plus the new ones. No production code has been touched, so any failure here is a test-authoring bug. (The exact baseline count drifts as unrelated suites land; the load-bearing check is that every pre-existing test still passes, not the specific total.)

- [ ] **Step 4: Commit**

```bash
git add server/tests/test_routes_search_signature.py
git commit -m "test(search): characterize the search signature endpoints"
```

**PR 1 ends here.** Open it, get it merged green, and only then start PR 2. That ordering is the whole point: tests merged before the extraction exists cannot have been fitted to the new behavior.

---

# PR 2 — Extraction

Lands against the merged, green safety net. Review question: *did anything move that shouldn't have?* Tasks 6-11 must not change a single response byte; **every PR 1 test stays green, unmodified, through Task 11.**

### Task 6: Delete the dead code first

Deleting before extracting (rather than after) means the extraction never has to reason about, move, or accidentally preserve code that has no callers. It also makes this the cheapest possible review: *do these five symbols really have no callers?* — a question `grep` answers, independent of everything else in the PR.

Every symbol below was confirmed callerless by `grep -rn "<name>" --include=*.py .` across the whole repo. This covers spec fix #1 (widened per Spec correction #2) and part of fix #4.

**Files:**
- Modify: `server/routes/search.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. Pure deletion — no symbol that survives this task changes.

- [ ] **Step 1: Confirm each symbol is dead**

Run:
```bash
for sym in create_condition format_attr_condition parse_attribute_var ATTRIBUTE_VAR_RE _map_mysql_operator; do
  echo "--- $sym"
  grep -rn "\b$sym\b" --include=*.py . | grep -v __pycache__
done
```
Expected: each symbol prints **only its own definition line** in `server/routes/search.py` (and, for `format_attr_condition`, the mention inside `format_attr_condition_with_definition`'s docstring — a different function, which stays). No call sites.

If any symbol shows a real caller, stop and remove it from this task — do not delete a live symbol to satisfy the plan.

- [ ] **Step 2: Delete them**

Remove from `server/routes/search.py`:
- `create_condition` (`210-224`) — callerless. Its `assert c["variable"] in fields_map` and its in-place `c["variable"] = fields_map[...]` mutation die with it, which is spec fix #4's "kill the mutation" in its entirety.
- `format_attr_condition` (`311-314`) — callerless legacy. **Keep** `format_attr_condition_with_definition` (297-308), which is live.
- `parse_attribute_var` (`230-236`) and `ATTRIBUTE_VAR_RE` (`227`) — callerless. The live attribute path uses `AttributeCondition`'s structured `model`/`variable`/`feature` fields, never `model[attr]` string parsing (Spec correction #3).
- `_map_mysql_operator` (`174-180`) — callerless. `format_condition` handles NULL semantics directly.
- The now-unused `import re` inside `parse_attribute_var` goes with it.

- [ ] **Step 3: Verify they are gone and nothing else moved**

Run:
```bash
grep -rn "create_condition\|format_attr_condition\b\|parse_attribute_var\|ATTRIBUTE_VAR_RE\|_map_mysql_operator" --include=*.py server orm | grep -v __pycache__
```
Expected: **no output** (`format_attr_condition_with_definition` does not match `format_attr_condition\b`).

- [ ] **Step 4: Run the full suite**

Run: `dev/.venv/bin/python -m pytest -q`
Expected: PASS. Deleting unreachable code cannot change behavior, and the PR 1 characterization tests prove it — in particular `test_unknown_static_field_is_rejected_by_pydantic`, which pins that the 422 comes from Pydantic and never depended on the deleted assert.

- [ ] **Step 5: Commit**

```bash
git add server/routes/search.py
git commit -m "refactor(search): delete dead condition helpers

create_condition, format_attr_condition, parse_attribute_var, ATTRIBUTE_VAR_RE
and _map_mysql_operator have no callers. Deleted before the extraction so the
move has less surface to reason about. No behavior change."
```

---

### Task 7: The search vocabulary (`fields.py`)

**Files:**
- Create: `server/services/search/__init__.py`
- Create: `server/services/search/fields.py`

**Interfaces:**
- Produces (consumed by Tasks 8, 9, 10, 11):
  - Literals `searchable_fields`, `study_searchable_fields`, `instance_order_by_fields`, `study_order_by_fields`, `operators`
  - Maps `instance_search_fields_map`, `study_search_fields_map`, `instance_order_by_fields_map`, `study_order_by_fields_map`
  - Aliases `ActiveSegmentation`, `ActiveFormAnnotation`, `SegCreator`, `FormCreator`, `SegTag`, `FormTag`, `InstTag`, `StudyTag`
  - Pydantic model `SignatureField`

- [ ] **Step 1: Create `server/services/search/fields.py`**

Move `search.py:52-171` (the aliases, Literals and maps) and `search.py:651-663` (`SignatureField`) **verbatim** — same names, same order, same values. The aliases must move with the maps: the maps reference them, and the repository's entity-partitioning compares against them by identity.

```python
"""The search vocabulary: UI labels, their ORM attributes, and the field signature.

Lives in ``services/`` because it has consumers in two layers -- ``routes/``
types its Pydantic ``variable`` fields with the Literals here, and
``SearchService`` resolves labels against the maps here. A symbol used by two
layers must live in the lower one.
"""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from eyened_orm import (
    Creator,
    DeviceModel,
    Feature,
    FormAnnotation,
    FormSchema,
    ImageInstance,
    Patient,
    Project,
    Segmentation,
    Study,
    Tag,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import aliased

ActiveSegmentation = aliased(
    Segmentation,
    select(Segmentation).filter(~Segmentation.Inactive).subquery(name="active_segmentation"),
    name="active_segmentation",
)
ActiveFormAnnotation = aliased(
    FormAnnotation,
    select(FormAnnotation).filter(~FormAnnotation.Inactive).subquery(name="active_form_annot"),
    name="active_form_annot",
)
SegCreator = aliased(Creator, name="seg_creator")
FormCreator = aliased(Creator, name="form_creator")
SegTag = aliased(Tag, name="seg_tag")
FormTag = aliased(Tag, name="form_tag")
InstTag = aliased(Tag, name="image_tag")
StudyTag = aliased(Tag, name="study_tag")

searchable_fields = Literal[
    "Image DBID",
    "Laterality",
    "Modality",
    "ETDRS Field",
    "Color Fundus Quality",
    "Study Date",
    "Patient Identifier",
    "Patient Sex",
    "Patient Birthdate",
    "Project Name",
    "Device Model ID",
    "Segmentation Feature Name",  # backward-compat
    "Segmentation Creator Name",
    "Segmentation Tag Name",
    "Form Schema Name",
    "Form Creator Name",
    "Form Tag Name",
    "Image Tag Name",
]

operators = Literal[">", "<", ">=", "<=", "==", "!=", "IN", "IS NULL"]

instance_search_fields_map: Dict[searchable_fields, Any] = {
    "Image DBID": ImageInstance.ImageInstanceID,
    "Laterality": ImageInstance.Laterality,
    "Modality": ImageInstance.Modality,
    "ETDRS Field": ImageInstance.ETDRSField,
    "Color Fundus Quality": ImageInstance.CFQuality,
    "Study Date": Study.StudyDate,
    "Patient Identifier": Patient.PatientIdentifier,
    "Patient Sex": Patient.Sex,
    "Patient Birthdate": Patient.BirthDate,
    "Project Name": Project.ProjectName,
    "Device Model ID": DeviceModel.DeviceModelID,
    "Segmentation Feature Name": Feature.FeatureName,
    "Segmentation Creator Name": SegCreator.CreatorName,
    "Segmentation Tag Name": SegTag.TagName,
    "Form Schema Name": FormSchema.SchemaName,
    "Form Creator Name": FormCreator.CreatorName,
    "Form Tag Name": FormTag.TagName,
    "Image Tag Name": InstTag.TagName,
}

study_searchable_fields = Literal[
    "Study Date",
    "Study Description",
    "Study Round",
    "Patient Identifier",
    "Patient Sex",
    "Patient Birthdate",
    "Project Name",
    "Form Schema Name",
    "Form Creator Name",
    "Form Tag Name",
    "Study Tag Name",
]

study_search_fields_map: Dict[study_searchable_fields, Any] = {
    "Study Date": Study.StudyDate,
    "Study Description": Study.StudyDescription,
    "Study Round": Study.StudyRound,
    "Patient Identifier": Patient.PatientIdentifier,
    "Patient Sex": Patient.Sex,
    "Patient Birthdate": Patient.BirthDate,
    "Project Name": Project.ProjectName,
    "Form Schema Name": FormSchema.SchemaName,
    "Form Creator Name": FormCreator.CreatorName,
    "Form Tag Name": FormTag.TagName,
    "Study Tag Name": StudyTag.TagName,
}

instance_order_by_fields = Literal["Study Date", "Patient Birthdate", "Date Inserted"]

instance_order_by_fields_map: Dict[instance_order_by_fields, Any] = {
    "Study Date": Study.StudyDate,
    "Patient Birthdate": Patient.BirthDate,
    "Date Inserted": ImageInstance.DateInserted,
}

study_order_by_fields = Literal["Study Date", "Patient Birthdate", "Date Inserted"]

study_order_by_fields_map: Dict[study_order_by_fields, Any] = {
    "Study Date": Study.StudyDate,
    "Patient Birthdate": Patient.BirthDate,
    "Date Inserted": Study.DateInserted,
}


class SignatureField(BaseModel):
    """Signature descriptor for a searchable field."""

    name: str
    # Either a primitive type marker or an enum of allowed values
    values: str | list[str]  # 'string' | 'int' | 'float' | 'date' | string[]
    type: Literal["default", "attribute"] = "default"
    model: Optional[str] = None
    feature: Optional[str] = None  # feature name for segmentation-based attributes
    nullable: bool = False
    # Free-text field that additionally supports matching several values at once
    # (rendered as an IN / multi-value editor on the client).
    multi: bool = False
```

- [ ] **Step 2: Create the package surface `server/services/search/__init__.py`**

`SearchService` and `get_search_service` do not exist until Task 8; add their imports then. Start with what exists:

```python
"""Search: the one non-CRUD service.

Search maps to a query language rather than a model, so it carries a vocabulary
(``fields``) and a DSL (``conditions``) that the CRUD services have no analogue
for. ``__all__`` is the real public surface -- ``conditions`` is internal by
omission.
"""
from .fields import (
    SignatureField,
    instance_order_by_fields,
    operators,
    searchable_fields,
    study_order_by_fields,
    study_searchable_fields,
)

__all__ = [
    "SignatureField",
    "instance_order_by_fields",
    "operators",
    "searchable_fields",
    "study_order_by_fields",
    "study_searchable_fields",
]
```

- [ ] **Step 3: Verify the package imports and the vocabulary is intact**

Run:
```bash
dev/.venv/bin/python -c "
from server.services.search import searchable_fields, study_searchable_fields
from server.services.search.fields import instance_search_fields_map, study_search_fields_map
import typing
assert set(typing.get_args(searchable_fields)) == set(instance_search_fields_map)
assert set(typing.get_args(study_searchable_fields)) == set(study_search_fields_map)
print('vocabulary OK:', len(instance_search_fields_map), 'instance,', len(study_search_fields_map), 'study')
"
```
Expected: `vocabulary OK: 18 instance, 11 study`

- [ ] **Step 4: Commit**

```bash
git add server/services/search/__init__.py server/services/search/fields.py
git commit -m "refactor(search): extract the search vocabulary into services/search/fields"
```

---

### Task 8: `SearchRepository` — pure query construction

The largest production move. Everything SQL-shaped lands here, **verbatim**, including the three known inefficiencies.

**Files:**
- Create: `orm/eyened_orm/repositories/search/__init__.py`
- Create: `orm/eyened_orm/repositories/search/aliases.py`
- Create: `orm/eyened_orm/repositories/search/conditions.py`
- Create: `orm/eyened_orm/repositories/search/exists.py`
- Create: `orm/eyened_orm/repositories/search/selects.py`
- Create: `orm/eyened_orm/repositories/search/repository.py`
- Modify: `server/services/search/fields.py` (import the aliases from here instead of defining them)
- Test: `orm/eyened_orm/tests/test_search_repository.py`

**Interfaces:**
- Consumes: `seed_search_dataset` (Task 2); the aliases move here from Task 7's `fields.py`.
- Produces (consumed by Tasks 9 and 10):
  - `ResolvedCondition(variable: Any, operator: str, value: Any = None)` — frozen dataclass; `variable` is an already-resolved ORM attribute.
  - `AttributeConditionSpec(attribute: str, operator: str, value: Any = None, model: str | None = None, feature: str | None = None)` — frozen dataclass.
  - `SearchRepository` with:
    - `search_instances(session, *, conditions: list[ResolvedCondition], attr_conditions: list[AttributeConditionSpec], order_by: Any, order: str, limit: int, offset: int) -> list[ImageInstance]`
    - `count_instances(session, *, conditions, attr_conditions) -> int`
    - `search_studies(session, *, conditions: list[ResolvedCondition], order_by: Any, order: str, limit: int, offset: int) -> list[Study]`
    - `count_studies(session, *, conditions) -> int`
    - `instances_for_studies(session, study_ids: list[int]) -> list[ImageInstance]`
  - `order_by` is a resolved ORM column (e.g. `Study.StudyDate`), never a UI label — UI vocabulary must not cross into `orm/`.

- [ ] **Step 1: Write the failing tests**

Create `orm/eyened_orm/tests/test_search_repository.py`:

```python
import pytest

from eyened_orm import ImageInstance, Patient, Project, Study
from eyened_orm.repositories.search import (
    AttributeConditionSpec,
    ResolvedCondition,
    SearchRepository,
)
from eyened_orm.utils.factories import seed_search_dataset


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


@pytest.fixture()
def repo():
    return SearchRepository()


def _ids(rows):
    return [r.PublicID for r in rows]


def _instances(repo, session, conditions=(), attr_conditions=(), limit=100, offset=0):
    return repo.search_instances(
        session,
        conditions=list(conditions),
        attr_conditions=list(attr_conditions),
        order_by=ImageInstance.DateInserted,
        order="ASC",
        limit=limit,
        offset=offset,
    )


def test_search_instances_excludes_inactive(repo, session, data):
    """The base instance select filters out inactive instances."""
    assert _ids(_instances(repo, session)) == ["img-a1", "img-a2", "img-b1"]


def test_count_instances_matches_the_search(repo, session, data):
    """count_instances counts the same predicate the search applies."""
    assert repo.count_instances(session, conditions=[], attr_conditions=[]) == 3


def test_search_instances_applies_a_base_condition(repo, session, data):
    """A condition on a base entity lands in the WHERE clause."""
    cond = ResolvedCondition(variable=Project.ProjectName, operator="==", value="Alpha")

    assert _ids(_instances(repo, session, [cond])) == ["img-a1", "img-a2"]


def test_search_instances_paginates(repo, session, data):
    """limit/offset window the ordered result."""
    assert _ids(_instances(repo, session, limit=2, offset=0)) == ["img-a1", "img-a2"]
    assert _ids(_instances(repo, session, limit=2, offset=2)) == ["img-b1"]


@pytest.mark.parametrize(
    "attr_name,value,expected",
    [("FeatureName", "feat-x", ["img-a1"]), ("FeatureName", "nope", [])],
)
def test_segmentation_exists_branch_positive_and_empty(
    repo, session, data, attr_name, value, expected
):
    """The segmentation EXISTS semijoin matches only annotated instances."""
    from eyened_orm import Feature

    cond = ResolvedCondition(
        variable=getattr(Feature, attr_name), operator="==", value=value
    )

    assert _ids(_instances(repo, session, [cond])) == expected


@pytest.mark.parametrize("value,expected", [("schema-x", ["img-a1"]), ("nope", [])])
def test_forms_exists_branch_positive_and_empty(repo, session, data, value, expected):
    """The forms EXISTS semijoin correlates image-level form annotations."""
    from eyened_orm import FormSchema

    cond = ResolvedCondition(variable=FormSchema.SchemaName, operator="==", value=value)

    assert _ids(_instances(repo, session, [cond])) == expected


@pytest.mark.parametrize("value,expected", [("img-tag", ["img-a1"]), ("nope", [])])
def test_image_tag_exists_branch_positive_and_empty(repo, session, data, value, expected):
    """The image-tag EXISTS semijoin matches only tagged instances."""
    from server.services.search.fields import InstTag  # noqa: PLC0415

    cond = ResolvedCondition(variable=InstTag.TagName, operator="==", value=value)

    assert _ids(_instances(repo, session, [cond])) == expected


@pytest.mark.parametrize("value,expected", [(5, ["img-a1"]), (99, [])])
def test_attribute_exists_branch_positive_and_empty(repo, session, data, value, expected):
    """The attribute EXISTS resolves the definition and filters the typed value column."""
    spec = AttributeConditionSpec(attribute="Quality", operator="==", value=value, model="M1")

    assert _ids(_instances(repo, session, attr_conditions=[spec])) == expected


def test_unresolvable_attribute_is_skipped(repo, session, data):
    """Today's behavior, preserved verbatim: an unresolved definition drops the predicate."""
    spec = AttributeConditionSpec(attribute="NoSuchAttr", operator="==", value=1)

    assert _ids(_instances(repo, session, attr_conditions=[spec])) == [
        "img-a1",
        "img-a2",
        "img-b1",
    ]


def test_search_studies_and_count(repo, session, data):
    """Study search returns ordered studies and counts the same predicate."""
    rows = repo.search_studies(
        session, conditions=[], order_by=Study.StudyDate, order="ASC", limit=100, offset=0
    )

    assert [s.StudyID for s in rows] == [data.studies["a"].StudyID, data.studies["b"].StudyID]
    assert repo.count_studies(session, conditions=[]) == 2


def test_search_studies_applies_a_base_condition(repo, session, data):
    """A study condition on a joined base entity lands in the WHERE clause."""
    cond = ResolvedCondition(variable=Patient.PatientIdentifier, operator="==", value="PAT-B")
    rows = repo.search_studies(
        session, conditions=[cond], order_by=Study.StudyDate, order="ASC", limit=100, offset=0
    )

    assert [s.StudyID for s in rows] == [data.studies["b"].StudyID]


def test_instances_for_studies_returns_active_instances(repo, session, data):
    """instances_for_studies returns the studies' active instances."""
    rows = repo.instances_for_studies(session, [data.studies["a"].StudyID])

    assert sorted(_ids(rows)) == ["img-a1", "img-a2"]


def test_instances_for_studies_with_no_ids_returns_empty(repo, session, data):
    """An empty study-id list returns no rows rather than every instance."""
    assert repo.instances_for_studies(session, []) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `dev/.venv/bin/python -m pytest orm/eyened_orm/tests/test_search_repository.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eyened_orm.repositories.search'`

- [ ] **Step 3: Write the `orm/eyened_orm/repositories/search/` package**

Move, **without rewriting**, from `server/routes/search.py` (line numbers are pre-Task-6; the dead symbols Task 6 removed are already gone and are deliberately absent from this list):

- → `search/conditions.py`: `format_condition` (183-207), `get_value_column_for_attribute` (239-251), `convert_search_value_to_attribute_type` (254-294), `format_attr_condition_with_definition` (297-308), `entity_of` (334-348), `partition_conditions_by_entity` (351-357), `and_expr` (360-365), plus the two new dataclasses.
- → `search/aliases.py`: the eight `aliased(...)` definitions (52-71), relocated from Task 7's `fields.py`.
- → `search/exists.py`: all six `exists_*` builders (374-648).
- → `search/selects.py`: `_build_study_select` (732-779), `_build_instance_select` (782-886), and the `selectinload` option-sets from the two route handlers (907-929, 1046-1068).
- → `search/repository.py`: the five public methods, which are new thin wrappers around the above.

Structural notes for the implementer:
- The internal condition carrier becomes `ResolvedCondition` (spec fix #5). Replace every `c["variable"]` / `c["operator"]` / `c.get("value")` with attribute access. `format_condition(variable, condition)` becomes `format_condition(condition: ResolvedCondition)`, reading `condition.variable` itself.
- **Do not import from `server`.** This is the constraint that drives the alias move. The repository partitions conditions by entity via `entity_of(...)`, which returns whatever alias object the caller resolved the attribute from — so the repository must compare against the **same alias objects** the vocabulary used. Since `orm/` may not import `server/`, the aliases move **down** into `search/aliases.py`, and Task 7's `fields.py` imports them from here (`server` → `orm` is legal):

  ```python
  # server/services/search/fields.py -- replace the local aliased(...) block with:
  from eyened_orm.repositories.search import (
      ActiveFormAnnotation,
      ActiveSegmentation,
      FormCreator,
      FormTag,
      InstTag,
      SegCreator,
      SegTag,
      StudyTag,
  )
  ```

  They are pure ORM constructs with no UI vocabulary in them, so `orm/` is their honest home, and one definition keeps the identity comparison sound. Task 7's tests already import `InstTag` from `fields`, which keeps working.
- `_map_mysql_operator` was **deleted in Task 6** as dead code — do not move it. `format_condition` handles NULL semantics directly.
- `search_instances` applies `.limit(limit + 1)` **at the service**, not here: the repository takes the already-computed `limit`/`offset` and applies them literally. The `limit + 1` lookahead is the service's pagination policy.
- `count_instances`/`count_studies` must keep reusing the same select via `select(func.count()).select_from(stmt.subquery())` — that is what makes the count provably agree with the search.
- `instances_for_studies` keeps its `.distinct()` verbatim, and must return `[]` for an empty `study_ids` list.

Sketch of `repository.py` (the moved bodies land in `conditions.py`/`exists.py`/`selects.py` unchanged; annotate every public signature — no bare `list`):

```python
"""Pure query construction for the search surfaces.

Framework-agnostic SQLAlchemy: takes a Session and already-resolved ORM
predicates, returns rows and counts. UI vocabulary never reaches this module --
callers resolve labels to ORM attributes before calling in.

Carries three known query-shape inefficiencies verbatim (the attribute-def N+1,
the OR-of-joins EXISTS, and the redundant DISTINCT in instances_for_studies).
They are deliberate follow-up work, gated on an EXPLAIN ANALYZE baseline against
real MySQL; the SQLite suite can prove rows are unchanged but not that a rewrite
is faster. Do not "fix" them here.
"""
from __future__ import annotations

from typing import Any, Literal

from eyened_orm import ImageInstance, Study
from sqlalchemy.orm import Session

from .conditions import AttributeConditionSpec, ResolvedCondition
from .selects import build_instance_select, build_study_select, instance_options


class SearchRepository:
    """Query construction and execution for instance and study search."""

    def search_instances(
        self,
        session: Session,
        *,
        conditions: list[ResolvedCondition],
        attr_conditions: list[AttributeConditionSpec],
        order_by: Any,
        order: Literal["ASC", "DESC"],
        limit: int,
        offset: int,
    ) -> list[ImageInstance]:
        """Return instances matching the conditions, ordered and windowed."""
        stmt = build_instance_select(session, conditions, attr_conditions, order_by, order)
        return list(
            session.execute(
                stmt.options(*instance_options()).limit(limit).offset(offset)
            ).scalars().all()
        )

    def count_instances(
        self,
        session: Session,
        *,
        conditions: list[ResolvedCondition],
        attr_conditions: list[AttributeConditionSpec],
    ) -> int:
        """Count instances matching the same predicate ``search_instances`` applies."""
        ...
```

And `conditions.py` holds the two carriers (`order_by` stays `Any`: `aliased()` attributes are not `InstrumentedAttribute`, so a narrower hint would be a lie):

```python
@dataclass(frozen=True)
class ResolvedCondition:
    """One condition whose ``variable`` is already an ORM attribute."""

    variable: Any
    operator: str
    value: Any = None


@dataclass(frozen=True)
class AttributeConditionSpec:
    """One attribute condition, still addressed by name (resolved against the DB here)."""

    attribute: str
    operator: str
    value: Any = None
    model: str | None = None
    feature: str | None = None
```

- [ ] **Step 4: Run the repository tests**

Run: `dev/.venv/bin/python -m pytest orm/eyened_orm/tests/test_search_repository.py -q`
Expected: PASS

- [ ] **Step 5: Confirm the layering constraint still holds**

Run: `grep -rn "^from server\|^import server" orm/eyened_orm --include=*.py | grep -v __pycache__`
Expected: **no output**. Any hit means the repository reached upward and the extraction is wrong.

- [ ] **Step 6: Commit**

```bash
git add orm/eyened_orm/repositories/search/ orm/eyened_orm/tests/test_search_repository.py server/services/search/fields.py
git commit -m "refactor(search): extract SearchRepository with pure query construction

Query construction moves into a repositories/search package (conditions,
exists, selects, repository) rather than one ~700-line module -- for scale,
the largest existing repository is 179 lines. The entity aliases move down
here so orm/ never imports server/; fields.py now imports them."
```

---

### Task 9: Condition translation (`conditions.py`)

**Files:**
- Create: `server/services/search/conditions.py`
- Test: `server/tests/test_search_conditions.py`

**Interfaces:**
- Consumes: `fields.py` maps (Task 7); `ResolvedCondition` / `AttributeConditionSpec` (Task 8).
- Produces (consumed by Task 10):
  - `translate_instance_conditions(raw: list[dict[str, Any]]) -> tuple[list[ResolvedCondition], list[AttributeConditionSpec]]`
  - `translate_study_conditions(raw: list[dict[str, Any]]) -> list[ResolvedCondition]`
  - `UnknownFieldError(BadRequestError)` — raised only for an unknown **static** label; unreachable via HTTP (Pydantic 422s first), kept as a guard for non-HTTP callers. It subclasses `BadRequestError` (not `ValueError`) so that if it ever *does* fire it degrades to a 400 through the registered `ServiceError` handler, rather than escaping the service layer as an unhandled `ValueError` and becoming a 500. Every other error raised from `server/services/` is a `ServiceError`; this stays consistent with that.

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_search_conditions.py`:

```python
import pytest

from eyened_orm import Project
from eyened_orm.repositories.search import (
    AttributeConditionSpec,
    ResolvedCondition,
)
from server.services.search.conditions import (
    UnknownFieldError,
    translate_instance_conditions,
    translate_study_conditions,
)


def test_translate_resolves_a_static_label_to_its_orm_attribute():
    """A default condition's UI label becomes the mapped ORM attribute."""
    static, attrs = translate_instance_conditions(
        [{"type": "default", "variable": "Project Name", "operator": "==", "value": "Alpha"}]
    )

    assert static == [ResolvedCondition(Project.ProjectName, "==", "Alpha")]
    assert attrs == []


def test_translate_partitions_attribute_conditions():
    """Attribute conditions are split out and keep their model/feature addressing."""
    static, attrs = translate_instance_conditions(
        [
            {
                "type": "attribute",
                "model": "M1",
                "variable": "Quality",
                "operator": "==",
                "value": 5,
                "feature": None,
            }
        ]
    )

    assert static == []
    assert attrs == [
        AttributeConditionSpec(attribute="Quality", operator="==", value=5, model="M1", feature=None)
    ]


def test_translate_does_not_mutate_its_input():
    """Translation copies; the caller's condition dicts are left untouched."""
    raw = [{"type": "default", "variable": "Project Name", "operator": "==", "value": "Alpha"}]

    translate_instance_conditions(raw)

    assert raw[0]["variable"] == "Project Name"


def test_translate_study_conditions_resolves_labels():
    """Study conditions carry no discriminator and resolve against the study map."""
    assert translate_study_conditions(
        [{"variable": "Project Name", "operator": "==", "value": "Beta"}]
    ) == [ResolvedCondition(Project.ProjectName, "==", "Beta")]


def test_unknown_static_label_raises():
    """An unknown static label raises rather than silently dropping the filter."""
    with pytest.raises(UnknownFieldError):
        translate_instance_conditions(
            [{"type": "default", "variable": "Nope", "operator": "==", "value": 1}]
        )
```

- [ ] **Step 2: Run to verify they fail**

Run: `dev/.venv/bin/python -m pytest server/tests/test_search_conditions.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.services.search.conditions'`

- [ ] **Step 3: Write `server/services/search/conditions.py`**

```python
"""Request DSL -> resolved condition objects.

No DB, no HTTP, no SQLAlchemy expression building: this module only maps UI
labels onto ORM attributes and splits the two condition kinds apart. Expression
construction belongs to ``SearchRepository``, which cannot import from
``server``.
"""
from __future__ import annotations

from typing import Any

from eyened_orm.repositories.search import (
    AttributeConditionSpec,
    ResolvedCondition,
)

from ..exceptions import BadRequestError
from .fields import instance_search_fields_map, study_search_fields_map


class UnknownFieldError(BadRequestError):
    """Raised when a static condition names a field outside the vocabulary.

    Unreachable over HTTP -- ``variable`` is Literal-typed, so Pydantic returns
    422 before a request reaches here. Kept as a guard for non-HTTP callers.

    Subclasses ``BadRequestError`` so an unexpected escape degrades to a 400 via
    the registered ServiceError handler instead of a 500. "Unreachable" plus
    "raises a bare ValueError from the service layer" is how latent 500s are born.
    """


def _resolve(raw: dict[str, Any], fields_map: dict[str, Any]) -> ResolvedCondition:
    label = raw["variable"]
    if label not in fields_map:
        raise UnknownFieldError(f"Invalid variable: {label}")
    return ResolvedCondition(
        variable=fields_map[label],
        operator=raw["operator"],
        value=raw.get("value"),
    )


def translate_instance_conditions(
    raw: list[dict[str, Any]],
) -> tuple[list[ResolvedCondition], list[AttributeConditionSpec]]:
    """Split instance conditions into resolved static conditions and attribute specs."""
    static: list[ResolvedCondition] = []
    attrs: list[AttributeConditionSpec] = []
    for cond in raw:
        if cond.get("type") == "attribute":
            attribute = cond.get("variable")
            if not isinstance(attribute, str):
                continue  # preserved verbatim: today's _build_instance_select skips these
            attrs.append(
                AttributeConditionSpec(
                    attribute=attribute,
                    operator=cond["operator"],
                    value=cond.get("value"),
                    model=cond.get("model"),
                    feature=cond.get("feature"),
                )
            )
        else:
            static.append(_resolve(cond, instance_search_fields_map))
    return static, attrs


def translate_study_conditions(raw: list[dict[str, Any]]) -> list[ResolvedCondition]:
    """Resolve study conditions against the study vocabulary."""
    return [_resolve(cond, study_search_fields_map) for cond in raw]
```

- [ ] **Step 4: Run the tests**

Run: `dev/.venv/bin/python -m pytest server/tests/test_search_conditions.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/services/search/conditions.py server/tests/test_search_conditions.py
git commit -m "refactor(search): extract condition-DSL translation"
```

---

### Task 10: `SearchService` — orchestration and the RBAC seam

**Files:**
- Create: `server/services/search/search_service.py`
- Modify: `server/services/search/__init__.py`
- Test: `server/tests/test_search_service.py`

**Interfaces:**
- Consumes: `SearchRepository` (Task 8), `translate_*_conditions` (Task 9), `fields.py` maps + `SignatureField` (Task 7).
- Produces (consumed by Task 11):
  - `InstanceSearchResult(instances: list[ImageInstance], studies: list[Study], count: int | None, has_more: bool, limit: int, page: int)`
  - `StudySearchResult(studies: list[Study], instances: list[ImageInstance], count: int | None, has_more: bool, limit: int, page: int)`
  - `SearchService(repository: SearchRepository)` with:
    - `search_instances(session, *, conditions, order_by, order, limit=200, page=0, include_count=False) -> InstanceSearchResult`
    - `search_studies(session, *, conditions, order_by, order, limit=200, page=0, include_count=False) -> StudySearchResult`
    - `instance_signature(session) -> list[SignatureField]`
    - `study_signature(session) -> list[SignatureField]`
  - `get_search_service() -> SearchService`
- The keyword signature is exactly what `SearchQuery.model_dump()` unpacks to, so the route calls `service.search_instances(db, **query.model_dump())`. The service must **not** import the route's Pydantic models — that is the inversion `ActingUser` exists to prevent.
- Read-only: no `ActingUser`, no audit logger, no `commit()`.

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_search_service.py`:

```python
import pytest

from eyened_orm.utils.factories import seed_search_dataset
from server.services.search import SearchService, get_search_service


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


@pytest.fixture()
def service():
    return get_search_service()


def _search(service, session, conditions=(), **kw):
    kw.setdefault("order_by", "Date Inserted")
    kw.setdefault("order", "ASC")
    return service.search_instances(session, conditions=list(conditions), **kw)


def test_get_search_service_returns_a_wired_service():
    """The factory wires a SearchService with its repository."""
    assert isinstance(get_search_service(), SearchService)


def test_search_instances_reports_has_more_without_leaking_the_lookahead_row(
    service, session, data
):
    """The limit+1 lookahead sets has_more but is trimmed from the results."""
    result = _search(service, session, limit=2, page=0)

    assert [i.PublicID for i in result.instances] == ["img-a1", "img-a2"]
    assert result.has_more is True


def test_search_instances_last_page_has_no_more(service, session, data):
    """The final page reports has_more False."""
    result = _search(service, session, limit=2, page=1)

    assert [i.PublicID for i in result.instances] == ["img-b1"]
    assert result.has_more is False


def test_search_instances_derives_studies_in_instance_order(service, session, data):
    """Studies are the instances' distinct studies, in first-appearance order."""
    result = _search(service, session)

    assert [s.StudyID for s in result.studies] == [
        data.studies["a"].StudyID,
        data.studies["b"].StudyID,
    ]


def test_search_instances_count_is_none_unless_requested(service, session, data):
    """count stays None unless include_count is set."""
    assert _search(service, session).count is None


def test_search_instances_count_ignores_pagination(service, session, data):
    """include_count counts the whole predicate, not the current page."""
    result = _search(service, session, limit=1, page=0, include_count=True)

    assert len(result.instances) == 1
    assert result.count == 3


def test_search_instances_with_no_matches_returns_empty_result(service, session, data):
    """A search matching nothing returns empty lists, not None."""
    result = _search(
        service,
        session,
        [{"type": "default", "variable": "Project Name", "operator": "==", "value": "Nope"}],
    )

    assert result.instances == []
    assert result.studies == []
    assert result.has_more is False


def test_search_studies_paginates_and_counts(service, session, data):
    """Study search applies the same limit+1/has_more and include_count policy."""
    result = service.search_studies(
        session, conditions=[], order_by="Study Date", order="ASC", limit=1, page=0,
        include_count=True,
    )

    assert [s.StudyID for s in result.studies] == [data.studies["a"].StudyID]
    assert result.has_more is True
    assert result.count == 2


def test_instance_signature_lists_the_vocabulary(service, session, data):
    """The instance signature covers the searchable fields plus seeded attributes."""
    names = {f.name for f in service.instance_signature(session)}

    assert "Project Name" in names
    assert "Quality" in names


def test_study_signature_lists_the_vocabulary(service, session, data):
    """The study signature covers the study searchable fields."""
    names = {f.name for f in service.study_signature(session)}

    assert "Study Tag Name" in names
```

- [ ] **Step 2: Run to verify they fail**

Run: `dev/.venv/bin/python -m pytest server/tests/test_search_service.py -q`
Expected: FAIL — `ImportError: cannot import name 'SearchService' from 'server.services.search'`

- [ ] **Step 3: Write `server/services/search/search_service.py`**

Move the orchestration out of the two route handlers (`search.py:889-1096`) and the two signature handlers (`search.py:1099-1257`) — the pagination arithmetic, the studies-from-instances derivation, the count call, and the signature assembly (including `_query_tag_names`). The `DTOConverter` calls stay behind in the route.

```python
"""Search orchestration: the RBAC seam.

Read-only: no ActingUser, no audit logger, no commit(). Takes explicit keyword
arguments rather than the route's Pydantic ``SearchQuery`` -- importing that
would invert the routes -> services dependency arrow. ``SearchQuery.model_dump()``
unpacks to exactly this signature.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from eyened_orm import ImageInstance, Study
from eyened_orm.repositories.search import SearchRepository
from sqlalchemy.orm import Session

from .conditions import translate_instance_conditions, translate_study_conditions
from .fields import (
    SignatureField,
    instance_order_by_fields_map,
    study_order_by_fields_map,
)


@dataclass
class InstanceSearchResult:
    instances: list[ImageInstance] = field(default_factory=list)
    studies: list[Study] = field(default_factory=list)
    count: int | None = None
    has_more: bool = False
    limit: int = 200
    page: int = 0


@dataclass
class StudySearchResult:
    studies: list[Study] = field(default_factory=list)
    instances: list[ImageInstance] = field(default_factory=list)
    count: int | None = None
    has_more: bool = False
    limit: int = 200
    page: int = 0


class SearchService:
    """Orchestrates search: translate the DSL, query, paginate, derive, count."""

    def __init__(self, repository: SearchRepository) -> None:
        self.repository = repository

    def search_instances(
        self,
        session: Session,
        *,
        conditions: list[dict[str, Any]],
        order_by: str,
        order: str,
        limit: int = 200,
        page: int = 0,
        include_count: bool = False,
    ) -> InstanceSearchResult:
        """Search instances, derive their studies, and optionally count the total."""
        static_conds, attr_conds = translate_instance_conditions(conditions)
        # RBAC Step 2 seam: append the visible-project predicate for the acting
        # user to `static_conds` here -- this is the one place both the search and
        # the count read, so a filter added here cannot be bypassed by either.
        # Inert pass-through today.
        offset = limit * page

        rows = self.repository.search_instances(
            session,
            conditions=static_conds,
            attr_conditions=attr_conds,
            order_by=instance_order_by_fields_map[order_by],
            order=order,
            limit=limit + 1,  # lookahead: one extra row answers has_more
            offset=offset,
        )
        has_more = len(rows) > limit
        instances = rows[:limit] if has_more else rows

        if not instances:
            return InstanceSearchResult(limit=limit, page=page)

        studies = self._studies_for(session, instances)
        count = None
        if include_count:
            count = self.repository.count_instances(
                session, conditions=static_conds, attr_conditions=attr_conds
            )
        return InstanceSearchResult(
            instances=list(instances),
            studies=studies,
            count=count,
            has_more=has_more,
            limit=limit,
            page=page,
        )
```

Implementation notes:
- `_studies_for` reproduces `search.py:950-976` exactly: walk instances in order, collect distinct `Series.Study.StudyID`, load those studies, re-sort into first-appearance order.
- `search_studies` mirrors `search.py:1004-1096`: page the studies, then `repository.instances_for_studies(session, study_ids)`, then re-sort studies into `study_ids` order.
- `instance_signature` / `study_signature` move `search.py:1107-1257` verbatim, returning `SignatureField` from `fields.py`. Keep the `_query_tag_names` helper as a private module function.
- Add `get_search_service() -> SearchService: return SearchService(SearchRepository())` at the bottom, matching `get_study_service()`.

- [ ] **Step 4: Export the service from the package**

Add to `server/services/search/__init__.py`:

```python
from .search_service import (
    InstanceSearchResult,
    SearchService,
    StudySearchResult,
    get_search_service,
)
```

and extend `__all__` with `"InstanceSearchResult"`, `"SearchService"`, `"StudySearchResult"`, `"get_search_service"`.

- [ ] **Step 5: Run the service tests**

Run: `dev/.venv/bin/python -m pytest server/tests/test_search_service.py -q`
Expected: PASS

- [ ] **Step 6: Confirm the layering constraint holds**

Run: `grep -rn "from server.routes\|from ..routes\|from ...routes" server/services --include=*.py | grep -v __pycache__`
Expected: **no output**.

- [ ] **Step 7: Commit**

```bash
git add server/services/search/search_service.py server/services/search/__init__.py server/tests/test_search_service.py
git commit -m "feat(services): add SearchService with the RBAC visibility seam"
```

---

### Task 11: Thin the route

The payoff task, and the one the characterization tests exist to police. **Every PR 1 test must stay green here, unmodified.**

**Files:**
- Modify: `server/routes/search.py` (1257 lines → roughly 150)

**Interfaces:**
- Consumes: everything from Tasks 7-10.
- Produces: no new public symbols. `router` keeps its name and its import path, so `server/main.py` needs no change.

- [ ] **Step 1: Rewrite `server/routes/search.py` as thin handlers**

Keep in this file **only**: the HTTP contracts (`DefaultCondition`, `AttributeCondition`, `SearchCondition`, `SearchQuery`, `SearchResponse`, `StudySearchCondition`, `StudySearchQuery`, `StudySearchResponse`) and the four handlers. `SignatureField` now comes from `services.search`.

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..dtos import ImageGET, StudyGET
from ..dtos.dto_converter import DTOConverter
from ..services.search import (
    SearchService,
    SignatureField,
    get_search_service,
    instance_order_by_fields,
    operators,
    searchable_fields,
    study_order_by_fields,
    study_searchable_fields,
)
from .auth import CurrentUser, get_current_user

router = APIRouter()

# ... the Pydantic contracts, unchanged from today ...


@router.post(
    "/instances/search", response_model=SearchResponse, response_model_exclude_none=True
)
async def search_instances(
    query: SearchQuery,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
):
    result = service.search_instances(db, **query.model_dump())
    return {
        "instances": [
            DTOConverter.image_instance_to_get(i, with_tag_metadata=True)
            for i in result.instances
        ],
        "studies": [
            DTOConverter.study_to_get(s, include_series=True, with_tag_metadata=True)
            for s in result.studies
        ],
        "limit": result.limit,
        "page": result.page,
        "count": result.count,
        "result_ids": [i.PublicID for i in result.instances],
        "has_more": result.has_more,
    }


@router.get("/instances/search/signature", response_model=list[SignatureField])
async def instances_signature(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
):
    """Return signature metadata for instance search fields."""
    return service.instance_signature(db)
```

`search_studies` and `studies_signature` follow the same shape (`result_ids` for studies is `[s.StudyID for s in result.studies]`).

- [ ] **Step 2: Verify nothing extraction-related was left behind (spec fixes #2, #4)**

The callerless helpers are already gone (Task 6). What must be true *now*, once the extraction is complete:
- `map_conditions_to_attrs`'s `assert v in fields_map` (`search.py:329`) is gone — it is superseded, not deleted in place: the function itself moves out and `translate_instance_conditions`/`translate_study_conditions` (Task 9) replace it, with `UnknownFieldError` where the assert was. The assert was unreachable anyway (`variable` is Literal-typed at both call sites, so Pydantic 422s first — pinned by `test_unknown_static_field_is_rejected_by_pydantic`).
- No mid-file or in-function imports survive (spec fix #4): the `from sqlalchemy import select as sa_select` at `search.py:371` and the in-function imports at `search.py:361` and `search.py:543` must land at the **top** of whichever module the code moved into. (`search.py:231`'s `import re` went with `parse_attribute_var` in Task 6.)
- The in-place `c["variable"] = fields_map[...]` mutation is gone with `create_condition` (Task 6), and `ResolvedCondition` being frozen makes the non-mutating copy the only option (pinned by `test_translate_does_not_mutate_its_input`).

- [ ] **Step 3: Verify the route is actually thin**

Run:
```bash
grep -rn "sa_select" --include=*.py server orm | grep -v __pycache__
```
Expected: **no output**.

Run: `grep -rnE "^\s+(import|from) " --include=*.py server/routes/search.py server/services/search orm/eyened_orm/repositories/search | grep -v __pycache__`
Expected: **no output** — every import sits at module top level.

Run: `grep -c "" server/routes/search.py`
Expected: roughly 150 (from 1257).

- [ ] **Step 4: Run the full suite — the behavior-preservation gate**

Run: `dev/.venv/bin/python -m pytest -q`
Expected: PASS, **every PR 1 characterization test included and unmodified**.

If a characterization test fails here, the extraction changed behavior. Fix the extraction, never the test. That rule is the entire reason PR 1 shipped first.

- [ ] **Step 5: Refresh the knowledge graph**

Run: `dev/.venv/bin/graphify update .`

- [ ] **Step 6: Commit**

```bash
git add server/routes/search.py
git commit -m "refactor(routes): reduce search endpoints to thin handlers

Route search through SearchService/SearchRepository. The unreachable
assert in map_conditions_to_attrs is superseded by UnknownFieldError, and
the mid-file imports are consolidated. Behavior and SQL shape unchanged."
```

---

### Task 12: Fail loudly on an unresolvable attribute

The spec's one open question, answered. **Optional — this is the only task in PR 2 that changes behavior. Skip it to keep silent-skip; nothing else depends on it.** See "The silent-skip decision" above for the reasoning and evidence.

**Files:**
- Modify: `server/services/search/search_service.py`
- Modify: `orm/eyened_orm/repositories/search/exists.py` and `search/repository.py`
- Modify: `orm/eyened_orm/tests/test_search_repository.py`
- Modify: `server/tests/test_search_service.py`
- Modify: `server/tests/test_routes_search_instances.py`

**Interfaces:**
- Produces: `SearchRepository.resolve_attribute_definitions(session, specs) -> dict[tuple[str | None, str, str | None], AttributeDefinition]` — the resolution step, surfaced so the service can detect misses and decide the policy. Keeping the *policy* in the service is the point: the repository stays a data-access module with no opinion about HTTP status codes.

- [ ] **Step 1: Write the failing tests**

In `server/tests/test_search_service.py`:

```python
def test_unresolvable_attribute_raises_bad_request(service, session, data):
    """An attribute that resolves to nothing is a 400, not a silently-dropped filter."""
    from server.services.exceptions import BadRequestError

    with pytest.raises(BadRequestError):
        _search(
            service,
            session,
            [{"type": "attribute", "model": None, "variable": "NoSuchAttr",
              "operator": "==", "value": 1}],
        )
```

In `server/tests/test_routes_search_instances.py`, replace the pinned silent-skip characterization with the new contract:

```python
def test_unknown_attribute_field_is_rejected(client, data):
    """An unresolvable attribute 400s rather than silently returning every row.

    Behavior change (was: filter dropped, full result set returned). See
    docs/superpowers/plans/2026-07-14-search-refactor.md Task 11.
    """
    resp = client.post(
        "/instances/search",
        json={
            "conditions": [
                {"type": "attribute", "model": None, "variable": "NoSuchAttr",
                 "operator": "==", "value": 1}
            ],
            "order_by": "Study Date",
            "order": "ASC",
        },
    )

    assert resp.status_code == 400
```

And update the repository's `test_unresolvable_attribute_is_skipped` docstring — the repository still skips; the *service* now rejects before the repository is asked.

- [ ] **Step 2: Run to verify they fail**

Run: `dev/.venv/bin/python -m pytest server/tests/test_search_service.py -k unresolvable -q`
Expected: FAIL — `DID NOT RAISE BadRequestError`

- [ ] **Step 3: Implement**

In `SearchRepository`, extract the definition-resolution loop out of `exists_attributes_for_instance` into `resolve_attribute_definitions(session, specs)` returning the `{(model, attribute, feature): AttributeDefinition}` dict (this is the same per-spec `db.execute` loop as today — still the N+1, still follow-up work, just now callable).

In `SearchService.search_instances`, between translation and the repository call:

```python
if attr_conds:
    resolved = self.repository.resolve_attribute_definitions(session, attr_conds)
    missing = [
        spec.attribute for spec in attr_conds
        if (spec.model, spec.attribute, spec.feature) not in resolved
    ]
    if missing:
        # Name the fix, not just the failure: the signature endpoint is the
        # authoritative list of attributes this surface accepts.
        raise BadRequestError(
            f"Unknown search attribute(s): {', '.join(sorted(set(missing)))}. "
            f"See GET /instances/search/signature for the available attributes."
        )
```

Import `BadRequestError` from `..exceptions` (the existing `ServiceError` hierarchy already has a registered handler that renders it as a 400).

- [ ] **Step 4: Run the full suite**

Run: `dev/.venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/services/search/search_service.py orm/eyened_orm/repositories/search/ \
        orm/eyened_orm/tests/test_search_repository.py server/tests/test_search_service.py \
        server/tests/test_routes_search_instances.py
git commit -m "fix(search): reject unresolvable attribute conditions with 400

An unresolved attribute definition dropped the predicate and returned the full
unfiltered result set. Verified not load-bearing: the client only offers
attributes enumerated by the signature endpoint."
```

---

## Follow-up work (not this plan)

Carried from the spec, plus what this plan found. None of it is in scope here.

- **RBAC Step 2:** fill the `SearchService` seam (Task 10, `search_instances`). Highest-stakes RBAC surface — a missing filter is a cross-project leak, so it warrants dedicated leak-path tests, **including both signature endpoints**, which enumerate cross-project project/creator/tag names and are pinned by Task 5.
- **Search query optimization** (all three gated on an `EXPLAIN ANALYZE` baseline against real MySQL — SQLite's planner is not MySQL's, so the suite can prove identical rows but never a speedup):
  1. **The attribute-def N+1** in `resolve_attribute_definitions` — one `db.execute` per unique `(model, attr, feature)`. Batch into one query. Strict win in any database; worth a query-count guard via a SQLAlchemy event listener.
  2. **The `OR`-of-joins `EXISTS`** — outer-joins `AttrVal → Segmentation → ModelSegmentation` and matches if any of three ID paths hits the instance; no planner can index that `OR`. Rewrite as three targeted `EXISTS` combined with `OR`. Trickiest, and the one that most needs the real-MySQL check.
  3. **The redundant `DISTINCT`** in `instances_for_studies` — each instance has exactly one `SeriesID`, so the join is 1:1 and cannot duplicate rows; the `DISTINCT` only forces a full-row sort.
- **Candidate indexes** (same `EXPLAIN ANALYZE` gate; each lands as its own migration PR, since indexes carry write-amplification cost): `ActiveFormAnnotation(ImageInstanceID)` and `(StudyID)`; the `*TagLink(…ID, TagID)` composite pairs; the `AttributeValue` FK columns; and `(order_col, PK)` composites matching the sorts.
- **`Study Instance UID`** (found by this plan, pinned by Task 5): `/studies/search/signature` advertises a field that `study_searchable_fields` omits, so searching it always 422s. Either add it to the Literal and the map (`Study.StudyInstanceUid`) or stop advertising it. Needs a product call on which, so it is not folded in here.
- **`async def` route handlers doing blocking sync DB I/O.** Every search handler is `async def` while `get_db` yields a **synchronous** SQLAlchemy `Session`, so `db.execute(...)` runs on the event loop and blocks it; FastAPI would otherwise run a plain `def` handler in a threadpool. This plan preserves it (the thin handlers stay `async def`) because changing it alters concurrency behavior, which is not a "structure only" change. It is **codebase-wide** — 82 `async def` handlers across `server/routes/` — so it wants one deliberate decision, not a drive-by fix here. Worth prioritizing on search specifically: it is the heaviest query surface in the app, so it is where event-loop blocking hurts most.
- **Oversized functions inside the repository.** `_build_instance_select` (105 lines) and `exists_attributes_for_instance` (~114) are well past the 20-50 line guidance. They move **verbatim** by design — decomposing them in the same change that relocates them would forfeit the behavior-preservation claim. Natural to fold into the query-optimization work above, which rewrites both anyway.

## Self-Review

**Spec coverage.** Every spec section maps to a task: the `SearchRepository` (Task 8), the `services/search/` package with `fields`/`conditions`/`search_service` and an `__all__` surface (Tasks 7, 9, 10), thin routes staying a flat module (Task 11), the RBAC seam (Task 10), characterization-tests-first across a two-PR split (Tasks 1-5 as PR 1), the reusable factory (Task 2), layered repository/service/route tests (Tasks 8, 10, 3-5), and fold-in fixes #1/#2/#4/#5 (Tasks 6, 9, 11) and the error-handling question (Task 12). Fix #3 is deliberately absent — it is stale, with evidence, per Spec correction #1.

**Deviations from the spec, all recorded above with evidence:** fix #3 dropped; fix #1 widened to `parse_attribute_var`/`ATTRIBUTE_VAR_RE`; the `model[attr]` narrative corrected; expression-building relocated from `services/conditions.py` into `orm/` to break a circular layering the spec did not notice; the service taking keywords rather than the route's Pydantic model; and `SignatureField` moving into `fields.py`. Fix #5 (the condition dataclass) is built into `conditions.py`/`search_repository.py` from the start rather than retrofitted after the move — retrofitting would touch every call site twice.

**Placeholders.** None. Every code step carries runnable code; every run step carries an exact command and expected output. The two largest risks — the TestClient harness and the factory — were executed against this codebase before this plan was written, and their tests pass.

**Type consistency.** `ResolvedCondition` and `AttributeConditionSpec` are defined once (Task 8, in `search/conditions.py`) and consumed under those names in Tasks 9 and 10. `translate_instance_conditions` returns the `(static, attrs)` tuple Task 10 unpacks. `SearchService`'s keyword signature matches `SearchQuery`'s fields (`conditions`, `limit`, `page`, `order_by`, `order`, `include_count`), which is what makes `**query.model_dump()` work in Task 11. `SignatureField` is defined once (Task 7) and used as the route's `response_model` (Task 11). The entity aliases are defined once (Task 8, `search/aliases.py`) and imported by `fields.py` — one definition, since the repository's `entity_of` partitioning compares them by identity. `seed_search_dataset` returns `SearchDataset` with `.images`/`.studies`/`.projects`, keyed as Tasks 3-5, 8 and 10 index them.

**Plan review (python-development skills).** Reviewed against `python-project-structure`, `python-design-patterns`, `python-error-handling`, `python-anti-patterns`, and `python-testing-patterns`. Four findings were applied: the repository became a package (a single module measured ~700 lines against a 179-line largest peer); dead-code deletion moved to Task 6, *before* the extraction ("delete before abstracting"); `UnknownFieldError` now subclasses `BadRequestError` rather than `ValueError`, so an "unreachable" raise degrades to 400 instead of 500; and the repository's public signatures are fully annotated (no bare `list`). Two findings were consciously **not** applied and recorded under Follow-up work instead: the `async def`-with-blocking-DB anti-pattern (codebase-wide, changes concurrency) and the oversized moved functions (decomposing them would forfeit the behavior-preservation claim). One skill recommendation is deliberately overridden: `python-project-structure` prefers absolute imports, while this plan follows the codebase's established mixed convention.
