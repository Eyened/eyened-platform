# Search Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the eight findings from the PR #165 review so the search Repository + Service extraction lands without two reachable 500s, without a 3x query regression, and with the layering it claims.

**Architecture:** Three correctness/efficiency fixes to the new search code (attribute-definition resolution, operator validation, resolve-once threading), then a layering pass that moves the last hand-built `select()` calls out of `SearchService` into `SearchRepository`, then two cleanups. No behavior changes beyond the two 500 -> 400/200 fixes; the 44 characterization tests must stay green **unmodified** throughout — they are the contract this branch exists to protect.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (ORM, `select()` style), FastAPI, Pydantic v2, pytest 8, SQLite in-memory test DB (`eyened_orm.utils.sqlite_testdb`).

## Global Constraints

- Branch: `feature/rbac-step1-service-layer`. Do **not** merge to `development`; this stacks onto open PR #165.
- Test runner: `dev/.venv/bin/python -m pytest` from the repo root. There is no `python`/`pytest` on PATH.
- Baseline to preserve: **354 passed**. Every task ends green. The count only ever goes up.
- The 44 characterization tests (`server/tests/test_routes_search_instances.py`, `test_routes_search_studies.py`, `test_routes_search_signature.py`) must **not** be edited except where a task explicitly says so (only Task 2 adds one, Task 3 adds one).
- `orm/` must never import from `server/`. `BadRequestError` lives in `server/services/exceptions.py` and is therefore unavailable inside `orm/` — validation that must produce a 400 belongs in `server/services/search/conditions.py`.
- The three documented query-shape inefficiencies (attribute-def N+1, OR-of-joins EXISTS, redundant DISTINCT in `instances_for_studies`) stay **as-is**. Task 3 changes how many *times* the N+1 runs, never its shape.
- Per repo CLAUDE.md: after modifying code run `dev/.venv/bin/graphify update .` (Task 8).
- Commit messages end with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Line numbers in the **Files** blocks are as-of commit `90ac766` and drift as earlier tasks land. Anchor edits on the quoted code, not the line number.

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `orm/eyened_orm/repositories/search/exists.py` | EXISTS builders + attribute-def resolution | 1, 3 |
| `orm/eyened_orm/repositories/search/selects.py` | base SELECT construction + eager-load option sets | 3 |
| `orm/eyened_orm/repositories/search/repository.py` | query execution; the `SearchRepository` public API | 3, 5, 6 |
| `server/services/search/conditions.py` | request DSL -> resolved conditions + request validation | 2 |
| `server/services/search/fields.py` | the UI vocabulary | 4 |
| `server/services/search/search_service.py` | orchestration + the RBAC seam | 2, 3, 5, 6 |
| `server/tests/conftest.py` | `client` fixture | 7 |
| `orm/eyened_orm/tests/test_search_repository.py` | repository tests | 1, 3, 5, 6 |
| `server/tests/test_search_service.py` | service tests | 2, 3 |
| `server/tests/test_search_conditions.py` | DSL translation tests | 2 |

---

### Task 1: Attribute resolution survives multi-version model names

Finding 1. `resolve_attribute_definitions` calls `scalar_one_or_none()` on a statement that joins `AttrDef -> AttributesModelOutput -> AttributesModel` and filters on `ModelName`. `Model` has `UniqueConstraint("ModelName", "Version")`, and migration `2026_06_30-fix_model_unique_constraints.py` **deliberately dropped** the ModelName-only unique index "so multiple versions of the same model name can coexist". Two versions of one model both producing an attribute therefore return two rows, and `scalar_one_or_none()` raises `MultipleResultsFound` -> 500.

Because `AttributeDefinition.AttributeName` has `UniqueConstraint("AttributeName", name="uq_AttributeDefinition_AttributeName")`, at most one *distinct* `AttrDef` can ever match. The duplicate rows are the **same** AttrDef, multiplied by the join fanout — so `.distinct()` collapses them losslessly and no version-precedence rule is needed. Keeping `scalar_one_or_none()` (rather than `.first()`) preserves the guard against a genuine invariant break.

**Files:**
- Modify: `orm/eyened_orm/repositories/search/exists.py:205-242` (`resolve_attribute_definitions`)
- Test: `orm/eyened_orm/tests/test_search_repository.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: no signature change. `SearchRepository.resolve_attribute_definitions(session, specs) -> dict[tuple[str | None, str, str | None], AttributeDefinition]` behaves identically except it no longer raises on multi-version model names.

- [ ] **Step 1: Write the failing test**

Append to `orm/eyened_orm/tests/test_search_repository.py`:

```python
def test_attribute_resolves_when_a_model_name_has_several_versions(repo, session, data):
    """Model allows (ModelName, Version) duplicates, so the def join fans out; resolution must not blow up."""
    from eyened_orm.attributes import AttributeDefinition
    from eyened_orm.repositories.search import AttributeConditionSpec
    from eyened_orm.utils.factories import make_attribute_value, make_attributes_model
    from sqlalchemy import select

    quality = session.scalar(
        select(AttributeDefinition).where(AttributeDefinition.AttributeName == "Quality")
    )
    m1_v2 = make_attributes_model(session, "M1", outputs=[quality], version="2")
    make_attribute_value(session, quality, image=data.images["a2"], model=m1_v2, value=5)
    session.flush()

    spec = AttributeConditionSpec(attribute="Quality", operator="==", value=5, model="M1")
    resolved = repo.resolve_attribute_definitions(session, [spec])

    assert resolved[("M1", "Quality", None)].AttributeName == "Quality"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/python -m pytest orm/eyened_orm/tests/test_search_repository.py::test_attribute_resolves_when_a_model_name_has_several_versions -v -p no:warnings`

Expected: FAIL with `sqlalchemy.exc.MultipleResultsFound: Multiple rows were found when one or none was required`

- [ ] **Step 3: Write minimal implementation**

In `orm/eyened_orm/repositories/search/exists.py`, in `resolve_attribute_definitions`, add `.distinct()` to the model-qualified branch. Replace:

```python
        if model_name:
            attr_def_stmt = (
                select(AttrDef)
                .join(
                    AttributesModelOutput,
                    AttrDef.AttributeID == AttributesModelOutput.AttributeID,
                )
                .join(
                    AttributesModel,
                    AttributesModelOutput.ModelID == AttributesModel.ModelID,
                )
                .where(AttributesModel.ModelName == model_name)
                .where(AttrDef.AttributeName == attr_name)
            )
```

with:

```python
        if model_name:
            # DISTINCT because Model allows several Versions per ModelName (see
            # migration 2026_06_30-fix_model_unique_constraints): the output join
            # returns one row per version, all of them the same AttributeDefinition.
            # AttributeName is uniquely constrained, so collapsing them is lossless
            # and scalar_one_or_none still guards a real invariant break.
            attr_def_stmt = (
                select(AttrDef)
                .join(
                    AttributesModelOutput,
                    AttrDef.AttributeID == AttributesModelOutput.AttributeID,
                )
                .join(
                    AttributesModel,
                    AttributesModelOutput.ModelID == AttributesModel.ModelID,
                )
                .where(AttributesModel.ModelName == model_name)
                .where(AttrDef.AttributeName == attr_name)
                .distinct()
            )
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `dev/.venv/bin/python -m pytest orm/eyened_orm/tests/test_search_repository.py -v -p no:warnings`
Expected: all PASS (12 existing + 1 new)

Run: `dev/.venv/bin/python -m pytest -q -p no:warnings`
Expected: `355 passed`

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/search/exists.py orm/eyened_orm/tests/test_search_repository.py
git commit -m "$(cat <<'EOF'
fix(search): resolve attributes when a model name has several versions

Model deliberately allows (ModelName, Version) duplicates, so the
AttributeDefinition -> AttributesModelOutput -> AttributesModel join fans out
one row per version and scalar_one_or_none() raised MultipleResultsFound -> 500.
AttributeName is uniquely constrained, so every duplicate row is the same
AttributeDefinition: DISTINCT collapses them losslessly, no version-precedence
rule needed, and the one-or-none guard still catches a real invariant break.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Reject `IN` with a non-list value as 400, not 500

Finding 2. `operators` advertises `"IN"` and `DefaultCondition.value` accepts `Union[date, int, float, str, list[str], None]`, so `{"operator": "IN", "value": "PAT-A"}` passes Pydantic. `format_condition` only reaches `variable.in_()` via its `isinstance(value, list)` branch; `IN` with a scalar matches no branch and hits `raise ValueError(f"Unsupported operator: {op}")`, which no handler maps -> 500.

`format_condition` lives in `orm/` and cannot import `BadRequestError`, so the check goes at the service boundary — the same place and the same precedent as Task 12's unresolvable-attribute 400. Note the DSL's existing leniency (a **list** value with **any** operator becomes `in_()`) is deliberately left alone: it is byte-preserved behavior and out of scope.

**Files:**
- Modify: `server/services/search/conditions.py`
- Test: `server/tests/test_search_conditions.py`, `server/tests/test_routes_search_instances.py`

**Interfaces:**
- Consumes: `BadRequestError` from `server/services/exceptions.py` (already imported in this module).
- Produces: `BadOperatorValueError(BadRequestError)` in `server/services/search/conditions.py`. `translate_instance_conditions` / `translate_study_conditions` keep their signatures and now raise it for `IN` + non-list.

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_search_conditions.py`:

```python
@pytest.mark.parametrize(
    "raw",
    [
        [{"type": "default", "variable": "Patient Identifier", "operator": "IN", "value": "PAT-A"}],
        [{"type": "attribute", "model": "M1", "variable": "Quality", "operator": "IN", "value": 5}],
    ],
    ids=["static", "attribute"],
)
def test_in_operator_requires_a_list_value(raw):
    """IN with a scalar has no SQL expression; reject it instead of raising ValueError downstream."""
    from server.services.search.conditions import BadOperatorValueError

    with pytest.raises(BadOperatorValueError):
        translate_instance_conditions(raw)


def test_in_operator_requires_a_list_value_on_the_study_surface():
    """The study DSL shares the same operator/value rule."""
    from server.services.search.conditions import BadOperatorValueError

    with pytest.raises(BadOperatorValueError):
        translate_study_conditions(
            [{"variable": "Patient Identifier", "operator": "IN", "value": "PAT-A"}]
        )
```

Append to `server/tests/test_routes_search_instances.py`:

```python
def test_in_operator_with_a_scalar_value_is_rejected(client, data):
    """PRE-EXISTING BUG fixed: IN + scalar raised an uncaught ValueError (500); now a 400."""
    resp = client.post(
        "/instances/search",
        json={
            "conditions": [
                {"type": "default", "variable": "Patient Identifier",
                 "operator": "IN", "value": "PAT-A"}
            ],
            "order_by": "Study Date",
            "order": "ASC",
        },
    )

    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `dev/.venv/bin/python -m pytest server/tests/test_search_conditions.py server/tests/test_routes_search_instances.py::test_in_operator_with_a_scalar_value_is_rejected -v -p no:warnings`

Expected: the two unit tests FAIL with `ImportError: cannot import name 'BadOperatorValueError'`; the route test FAILS with `ValueError: Unsupported operator: IN`

- [ ] **Step 3: Write minimal implementation**

In `server/services/search/conditions.py`, add the exception class after `UnknownFieldError`:

```python
class BadOperatorValueError(BadRequestError):
    """Raised when an operator/value pair has no SQL expression.

    ``format_condition`` reaches ``variable.in_()`` only through its
    ``isinstance(value, list)`` branch, so ``IN`` with a scalar falls through to a
    bare ``ValueError`` -- a 500 for what is plainly a bad request. That helper
    lives in ``orm/`` and cannot import ``BadRequestError``, so the check belongs
    here, at the same boundary that rejects unresolvable attributes.
    """
```

Add the validator below it:

```python
def _validate_operator_value(operator: str, value: Any) -> None:
    """Reject operator/value pairs the expression builder cannot express."""
    if operator == "IN" and not isinstance(value, list):
        raise BadOperatorValueError(
            f"Operator 'IN' requires a list value, got {type(value).__name__}."
        )
```

Call it from `_resolve`:

```python
def _resolve(raw: dict[str, Any], fields_map: dict[str, Any]) -> ResolvedCondition:
    label = raw["variable"]
    if label not in fields_map:
        raise UnknownFieldError(f"Invalid variable: {label}")
    _validate_operator_value(raw["operator"], raw.get("value"))
    return ResolvedCondition(
        variable=fields_map[label],
        operator=raw["operator"],
        value=raw.get("value"),
    )
```

And from the attribute branch of `translate_instance_conditions` — replace:

```python
            attrs.append(
                AttributeConditionSpec(
                    attribute=attribute,
                    operator=cond["operator"],
                    value=cond.get("value"),
                    model=cond.get("model"),
                    feature=cond.get("feature"),
                )
            )
```

with:

```python
            _validate_operator_value(cond["operator"], cond.get("value"))
            attrs.append(
                AttributeConditionSpec(
                    attribute=attribute,
                    operator=cond["operator"],
                    value=cond.get("value"),
                    model=cond.get("model"),
                    feature=cond.get("feature"),
                )
            )
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `dev/.venv/bin/python -m pytest -q -p no:warnings`
Expected: `359 passed`

- [ ] **Step 5: Commit**

```bash
git add server/services/search/conditions.py server/tests/test_search_conditions.py server/tests/test_routes_search_instances.py
git commit -m "$(cat <<'EOF'
fix(search): reject IN with a non-list value with 400

operators advertises IN and the Pydantic value union accepts a scalar, but
format_condition only reaches variable.in_() via its isinstance(value, list)
branch -- so IN + scalar fell through to a bare ValueError and 500ed. Same
failure class as the unresolvable attribute Task 12 fixed, so it gets the same
treatment at the same boundary: format_condition lives in orm/ and cannot import
BadRequestError, so the check goes in the service DSL translation.

The DSL's existing leniency (a list value with any operator becomes IN) is
byte-preserved and left alone.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Resolve attribute definitions once per request

Finding 3. Verified by counting SQL: one search with a single attribute condition and `include_count=True` issues **3** attribute-def resolution round-trips (2 without count); the old route issued **1**. Paths: (a) `SearchService.search_instances` resolves for the 400 check, (b) `build_instance_select` -> `exists_attributes_for_instance` resolves again, (c) `count_instances` -> `instance_filtered_select` -> `exists_attributes_for_instance` a third time. Since resolution is itself an N+1 (one query per unique key), a search with k unique keys went from k to 3k queries.

Fix: the service already resolves; thread the result down instead of re-resolving. `exists_attributes_for_instance` stops taking a `Session` and takes the resolved map, which also drops `session` out of `instance_filtered_select` / `build_instance_select` entirely. The N+1 **shape** is untouched — it just runs once.

**Files:**
- Modify: `orm/eyened_orm/repositories/search/exists.py:245-265` (`exists_attributes_for_instance`)
- Modify: `orm/eyened_orm/repositories/search/selects.py:122-210` (`instance_filtered_select`, `build_instance_select`)
- Modify: `orm/eyened_orm/repositories/search/repository.py:37-71` (`search_instances`, `count_instances`)
- Modify: `server/services/search/search_service.py:88-150` (`search_instances`)
- Test: `orm/eyened_orm/tests/test_search_repository.py`, `server/tests/test_search_service.py`

**Interfaces:**
- Consumes: `resolve_attribute_definitions` from Task 1 (unchanged signature).
- Produces:
  - `exists_attributes_for_instance(attr_conds: List[Tuple[Optional[str], str, Optional[str], Dict[str, Any]]], attr_defs: Dict[Tuple[Optional[str], str, Optional[str]], AttrDef]) -> Any` — `db` param **removed**.
  - `instance_filtered_select(conditions, attr_conditions, attr_defs)` — `session` param **removed**.
  - `build_instance_select(conditions, attr_conditions, attr_defs, order_by, order)` — `session` param **removed**.
  - `SearchRepository.search_instances(session, *, conditions, attr_conditions, attr_defs, order_by, order, limit, offset)` — new required kwarg `attr_defs`.
  - `SearchRepository.count_instances(session, *, conditions, attr_conditions, attr_defs)` — new required kwarg `attr_defs`.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_search_service.py`:

```python
def test_attribute_definitions_are_resolved_once_per_search(service, session, data):
    """The resolution N+1 runs once, not once per select build (validate + search + count)."""
    from sqlalchemy import event

    stmts: list[str] = []

    def _rec(conn, cursor, statement, params, context, executemany):
        stmts.append(" ".join(statement.split()))

    bind = session.get_bind()
    event.listen(bind, "before_cursor_execute", _rec)
    try:
        _search(
            service,
            session,
            [{"type": "attribute", "model": "M1", "variable": "Quality",
              "operator": "==", "value": 5}],
            include_count=True,
        )
    finally:
        event.remove(bind, "before_cursor_execute", _rec)

    resolutions = [
        s for s in stmts
        if s.startswith(
            'SELECT "AttributeDefinition"."AttributeID", '
            '"AttributeDefinition"."AttributeName"'
        )
    ]
    assert len(resolutions) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `dev/.venv/bin/python -m pytest server/tests/test_search_service.py::test_attribute_definitions_are_resolved_once_per_search -v -p no:warnings`

Expected: FAIL with `assert 3 == 1`

- [ ] **Step 3a: Take the session out of the EXISTS builder**

In `orm/eyened_orm/repositories/search/exists.py`, replace the head of `exists_attributes_for_instance`:

```python
def exists_attributes_for_instance(
    attr_conds: List[Tuple[Optional[str], str, Optional[str], Dict[str, Any]]],
    db: Session,
) -> Any:
    """EXISTS subqueries for attributes correlated by ImageInstance."""
    if not attr_conds:
        return None

    keys = [
        (model_name, attr_name, feature_name)
        for model_name, attr_name, feature_name, c in attr_conds
    ]
    attr_defs = resolve_attribute_definitions(db, keys)

    and_predicates = []
```

with:

```python
def exists_attributes_for_instance(
    attr_conds: List[Tuple[Optional[str], str, Optional[str], Dict[str, Any]]],
    attr_defs: Dict[Tuple[Optional[str], str, Optional[str]], AttrDef],
) -> Any:
    """EXISTS subqueries for attributes correlated by ImageInstance.

    Takes the already-resolved definitions rather than resolving them: the caller
    resolves once per request and hands the map to both the search and the count,
    which used to rebuild (and re-resolve) it independently. An unresolved key is
    still skipped here -- the service rejects it upstream with a 400.
    """
    if not attr_conds:
        return None

    and_predicates = []
```

The loop body below (`for model_name, attr_name, feature_name, c in attr_conds:` onward) is **unchanged**.

- [ ] **Step 3b: Take the session out of the select builders**

In `orm/eyened_orm/repositories/search/selects.py`:

Change the import line `from sqlalchemy.orm import Session, selectinload` to:

```python
from sqlalchemy.orm import selectinload
```

Add `AttrDef` to the conditions import so the new annotation resolves — replace:

```python
from .conditions import (
    AttributeConditionSpec,
    ResolvedCondition,
    and_expr,
    partition_conditions_by_entity,
)
```

with:

```python
from eyened_orm.attributes import AttributeDefinition as AttrDef

from .conditions import (
    AttributeConditionSpec,
    ResolvedCondition,
    and_expr,
    partition_conditions_by_entity,
)
```

Replace the `instance_filtered_select` signature:

```python
def instance_filtered_select(
    session: Session,
    conditions: Sequence[ResolvedCondition],
    attr_conditions: Sequence[AttributeConditionSpec],
):
```

with:

```python
def instance_filtered_select(
    conditions: Sequence[ResolvedCondition],
    attr_conditions: Sequence[AttributeConditionSpec],
    attr_defs: Dict[Tuple[Optional[str], str, Optional[str]], AttrDef],
):
```

Replace the attribute-EXISTS call inside it:

```python
    attr_exists = exists_attributes_for_instance(attr_conds_raw, session)
```

with:

```python
    attr_exists = exists_attributes_for_instance(attr_conds_raw, attr_defs)
```

Replace `build_instance_select`:

```python
def build_instance_select(
    session: Session,
    conditions: Sequence[ResolvedCondition],
    attr_conditions: Sequence[AttributeConditionSpec],
    order_by: Any,
    order: str,
):
    """The filtered instance select plus ordering (resolved order column + PK tiebreaker)."""
    q = instance_filtered_select(session, conditions, attr_conditions)
    sort_dir = order_by.asc() if order == "ASC" else order_by.desc()
    return q.order_by(sort_dir, ImageInstance.ImageInstanceID.asc())
```

with:

```python
def build_instance_select(
    conditions: Sequence[ResolvedCondition],
    attr_conditions: Sequence[AttributeConditionSpec],
    attr_defs: Dict[Tuple[Optional[str], str, Optional[str]], AttrDef],
    order_by: Any,
    order: str,
):
    """The filtered instance select plus ordering (resolved order column + PK tiebreaker)."""
    q = instance_filtered_select(conditions, attr_conditions, attr_defs)
    sort_dir = order_by.asc() if order == "ASC" else order_by.desc()
    return q.order_by(sort_dir, ImageInstance.ImageInstanceID.asc())
```

Update the typing import at the top of the file — replace:

```python
from typing import Any, Dict, List, Sequence
```

with:

```python
from typing import Any, Dict, List, Optional, Sequence, Tuple
```

- [ ] **Step 3c: Thread `attr_defs` through the repository**

In `orm/eyened_orm/repositories/search/repository.py`, replace `search_instances` and `count_instances`:

```python
    def search_instances(
        self,
        session: Session,
        *,
        conditions: List[ResolvedCondition],
        attr_conditions: List[AttributeConditionSpec],
        attr_defs: dict[tuple[str | None, str, str | None], AttributeDefinition],
        order_by: Any,
        order: Literal["ASC", "DESC"],
        limit: int,
        offset: int,
    ) -> List[ImageInstance]:
        """Return instances matching the conditions, ordered and windowed.

        ``attr_defs`` comes from ``resolve_attribute_definitions``; the caller
        resolves once and passes the same map to ``count_instances`` so the two
        agree without paying for the resolution twice.
        """
        stmt = build_instance_select(
            conditions, attr_conditions, attr_defs, order_by, order
        )
        return list(
            session.execute(
                stmt.options(*instance_options()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )

    def count_instances(
        self,
        session: Session,
        *,
        conditions: List[ResolvedCondition],
        attr_conditions: List[AttributeConditionSpec],
        attr_defs: dict[tuple[str | None, str, str | None], AttributeDefinition],
    ) -> int:
        """Count instances matching the same predicate ``search_instances`` applies."""
        stmt = instance_filtered_select(conditions, attr_conditions, attr_defs)
        return session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
```

- [ ] **Step 3d: Resolve once in the service**

In `server/services/search/search_service.py`, replace the body of `search_instances` from `static_conds, attr_conds = ...` down to the `count = ...` block:

```python
        static_conds, attr_conds = translate_instance_conditions(conditions)
        attr_defs: dict[tuple[str | None, str, str | None], Any] = {}
        if attr_conds:
            # Resolved once here and handed to both the search and the count: the
            # resolution is an N+1, so rebuilding it per select tripled the queries.
            attr_defs = self.repository.resolve_attribute_definitions(session, attr_conds)
            missing = [
                spec.attribute
                for spec in attr_conds
                if (spec.model, spec.attribute, spec.feature) not in attr_defs
            ]
            if missing:
                # Name the fix, not just the failure: the signature endpoint is the
                # authoritative list of attributes this surface accepts. A dropped
                # attribute filter would otherwise return the whole result set.
                raise BadRequestError(
                    f"Unknown search attribute(s): {', '.join(sorted(set(missing)))}. "
                    f"See GET /instances/search/signature for the available attributes."
                )
        # RBAC Step 2 seam: append the visible-project predicate for the acting
        # user to `static_conds` here -- this is the one place both the search and
        # the count read, so a filter added here cannot be bypassed by either.
        # Inert pass-through today.
        offset = limit * page

        rows = self.repository.search_instances(
            session,
            conditions=static_conds,
            attr_conditions=attr_conds,
            attr_defs=attr_defs,
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
                session,
                conditions=static_conds,
                attr_conditions=attr_conds,
                attr_defs=attr_defs,
            )
```

- [ ] **Step 3e: Update the repository test helper**

In `orm/eyened_orm/tests/test_search_repository.py`, replace `_instances`:

```python
def _instances(repo, session, conditions=(), attr_conditions=(), limit=100, offset=0):
    specs = list(attr_conditions)
    attr_defs = repo.resolve_attribute_definitions(session, specs) if specs else {}
    return repo.search_instances(
        session,
        conditions=list(conditions),
        attr_conditions=specs,
        attr_defs=attr_defs,
        order_by=ImageInstance.DateInserted,
        order="ASC",
        limit=limit,
        offset=offset,
    )
```

And replace `test_count_instances_matches_the_search`:

```python
def test_count_instances_matches_the_search(repo, session, data):
    """count_instances counts the same predicate the search applies."""
    assert repo.count_instances(session, conditions=[], attr_conditions=[], attr_defs={}) == 3
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `dev/.venv/bin/python -m pytest server/tests/test_search_service.py::test_attribute_definitions_are_resolved_once_per_search -v -p no:warnings`
Expected: PASS

Run: `dev/.venv/bin/python -m pytest -q -p no:warnings`
Expected: `360 passed` — and specifically the 44 characterization tests pass **unmodified**, proving the SQL is unchanged.

- [ ] **Step 5: Commit**

```bash
git add orm/eyened_orm/repositories/search/exists.py orm/eyened_orm/repositories/search/selects.py orm/eyened_orm/repositories/search/repository.py orm/eyened_orm/tests/test_search_repository.py server/services/search/search_service.py server/tests/test_search_service.py
git commit -m "$(cat <<'EOF'
perf(search): resolve attribute definitions once per request

The service resolved for its 400 check, build_instance_select resolved again,
and count_instances resolved a third time -- 3 round-trips where the old route
did 1 (verified by counting SQL). Since resolution is an N+1, a search with k
unique attribute keys cost 3k queries.

The service already resolves, so thread the map down instead of re-resolving:
exists_attributes_for_instance now takes attr_defs rather than a Session, which
drops session out of instance_filtered_select/build_instance_select entirely.
The N+1 shape is untouched (still gated follow-up) -- it just runs once. All 44
characterization tests stay green unmodified: the SQL is unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Delete the dead re-exports in `fields.py`

Finding 4. `fields.py` imports `ActiveFormAnnotation` and `ActiveSegmentation` behind `# noqa: F401  (re-exported: tests import InstTag from here)`. The comment is false: nothing imports either symbol from `server.services.search.fields`, and the one test that imports `InstTag` takes it from `eyened_orm.repositories.search` (`orm/eyened_orm/tests/test_search_repository.py:91`). Neither symbol is used in `fields.py` itself. The noqa suppresses the linter that would have caught this and misdirects the next reader into preserving imports with no consumer.

**Files:**
- Modify: `server/services/search/fields.py:21-30`

**Interfaces:**
- Consumes: nothing.
- Produces: `server.services.search.fields` no longer re-exports `ActiveFormAnnotation` / `ActiveSegmentation`. Both remain available from `eyened_orm.repositories.search`, which is where every real consumer already imports them.

- [ ] **Step 1: Prove the symbols have no consumer**

Run:

```bash
grep -rn "ActiveSegmentation\|ActiveFormAnnotation" --include=*.py server orm | grep -v "repositories/search"
```

Expected: only the two lines in `server/services/search/fields.py`. If anything else appears, stop and reassess — the comment would be right after all.

- [ ] **Step 2: Remove the dead imports**

In `server/services/search/fields.py`, replace:

```python
from eyened_orm.repositories.search import (
    ActiveFormAnnotation,  # noqa: F401  (re-exported: tests import InstTag from here)
    ActiveSegmentation,  # noqa: F401
    FormCreator,
    FormTag,
    InstTag,
    SegCreator,
    SegTag,
    StudyTag,
)
```

with:

```python
from eyened_orm.repositories.search import (
    FormCreator,
    FormTag,
    InstTag,
    SegCreator,
    SegTag,
    StudyTag,
)
```

- [ ] **Step 3: Run the tests and make sure they pass**

Run: `dev/.venv/bin/python -m pytest -q -p no:warnings`
Expected: `360 passed`

- [ ] **Step 4: Commit**

```bash
git add server/services/search/fields.py
git commit -m "$(cat <<'EOF'
refactor(search): drop dead alias re-exports from fields

ActiveFormAnnotation/ActiveSegmentation were imported into fields.py behind a
noqa whose stated reason ("tests import InstTag from here") is false: nothing
imports either symbol from fields, and the InstTag test imports from
eyened_orm.repositories.search. Neither is used in fields.py itself.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Move the study-derivation query into the repository

Findings 5 and part of 6. `SearchService._studies_for` inlines the exact eager-load chain that `selects.study_options()` already defines and `repository.search_studies` already uses — two copies of one loader, in different packages and different layers, that drift silently (a change to the study eager-load contract would make the studies block of `/instances/search` diverge from `/studies/search`, including its N+1 profile, with no test to catch it).

The split: the **query** goes to the repository; the **ordering** (first-appearance order of the instances) stays in the service, because that is orchestration, not data access.

**Files:**
- Modify: `orm/eyened_orm/repositories/search/repository.py`
- Modify: `server/services/search/search_service.py:201-228` (`_studies_for`)
- Test: `orm/eyened_orm/tests/test_search_repository.py`

**Interfaces:**
- Consumes: `study_options()` from `orm/eyened_orm/repositories/search/selects.py` (already imported in `repository.py`).
- Produces: `SearchRepository.studies_by_ids(session: Session, study_ids: List[int]) -> List[Study]` — studies with active instances eager-loaded, **unordered** (caller orders).

- [ ] **Step 1: Write the failing test**

Append to `orm/eyened_orm/tests/test_search_repository.py`:

```python
def test_studies_by_ids_loads_the_requested_studies(repo, session, data):
    """studies_by_ids returns exactly the requested studies, active instances loaded."""
    rows = repo.studies_by_ids(session, [data.studies["a"].StudyID])

    assert [s.StudyID for s in rows] == [data.studies["a"].StudyID]
    assert sorted(i.PublicID for s in rows for ser in s.Series for i in ser.ImageInstances) == [
        "img-a1",
        "img-a2",
    ]


def test_studies_by_ids_with_no_ids_returns_empty(repo, session, data):
    """An empty id list returns no rows rather than every study."""
    assert repo.studies_by_ids(session, []) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `dev/.venv/bin/python -m pytest orm/eyened_orm/tests/test_search_repository.py -k studies_by_ids -v -p no:warnings`
Expected: FAIL with `AttributeError: 'SearchRepository' object has no attribute 'studies_by_ids'`

- [ ] **Step 3: Add the repository method**

In `orm/eyened_orm/repositories/search/repository.py`, add after `search_studies`:

```python
    def studies_by_ids(self, session: Session, study_ids: List[int]) -> List[Study]:
        """Return the given studies with their active instances eager-loaded.

        Unordered -- the caller owns the ordering, which on the instances surface
        is the instances' first-appearance order and not a property of the query.
        """
        if not study_ids:
            return []
        stmt = (
            select(Study)
            .where(Study.StudyID.in_(study_ids))
            .options(*study_options())
        )
        return list(session.execute(stmt).scalars().all())
```

- [ ] **Step 4: Point the service at it**

In `server/services/search/search_service.py`, replace `_studies_for`:

```python
    def _studies_for(
        self, session: Session, instances: list[ImageInstance]
    ) -> List[Study]:
        """Distinct studies of the instances, in first-appearance order, series-loaded."""
        seen: set[int] = set()
        study_ids_ordered: list[int] = []
        for inst in instances:
            st = inst.Series.Study if inst.Series and inst.Series.Study else None
            if st and st.StudyID not in seen:
                seen.add(st.StudyID)
                study_ids_ordered.append(st.StudyID)

        studies = self.repository.studies_by_ids(session, study_ids_ordered)
        s_order = {sid: i for i, sid in enumerate(study_ids_ordered)}
        studies.sort(key=lambda s: s_order[s.StudyID])
        return studies
```

- [ ] **Step 5: Run the tests and make sure they pass**

Run: `dev/.venv/bin/python -m pytest -q -p no:warnings`
Expected: `362 passed` — `test_studies_are_derived_from_instances_in_instance_order` (characterization) still green unmodified.

- [ ] **Step 6: Commit**

```bash
git add orm/eyened_orm/repositories/search/repository.py orm/eyened_orm/tests/test_search_repository.py server/services/search/search_service.py
git commit -m "$(cat <<'EOF'
refactor(search): move study derivation query into the repository

_studies_for inlined the exact selectinload chain study_options() already
defines and search_studies already uses -- two copies of one eager-load
contract, in two layers, free to drift. The query moves to
SearchRepository.studies_by_ids; the first-appearance ordering stays in the
service, where it belongs (orchestration, not data access).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Move the signature queries into the repository

Findings 6 and 7. `SearchService` still hand-builds and executes `select()` statements in `_query_tag_names` and the two signature methods, contradicting the layering this PR exists to establish, and `study_signature` re-implements `_query_tag_names` twice while the helper sits at the top of the same module and `instance_signature` uses it — three implementations of one query shape in one file.

**The line this task draws:** no `select()` construction in `server/services/search/`. Calls to the existing `Model.query_column(session, col)` ORM helper **stay** in the service — they are an established codebase pattern, `instance_signature` already uses them, and they are not query construction. The enforceable outcome is that `select` and `selectinload` disappear from `search_service.py`'s imports.

This also documents the RBAC Step 2 consequence honestly: the signature endpoints enumerate every project/creator/tag across all projects and do **not** pass through the `static_conds` seam. This task does not fix that leak (it is Step 2 work, and the characterization tests pin today's behavior) — it puts the queries somewhere a Step 2 filter can actually reach.

**Files:**
- Modify: `orm/eyened_orm/repositories/search/repository.py`
- Modify: `server/services/search/search_service.py` — the import header, the `_query_tag_names` helper, and both signature methods
- Test: `orm/eyened_orm/tests/test_search_repository.py`

**Interfaces:**
- Consumes: `SearchRepository` from Task 5.
- Produces, all on `SearchRepository`:
  - `tag_names(session: Session, link_table: Any) -> List[str]` — distinct tag names via the link table, sorted.
  - `active_form_creator_names(session: Session) -> List[str]` — creators with >=1 active form annotation, sorted.
  - `attribute_signature_rows(session: Session) -> List[Tuple[str, AttributeDataType, Optional[str]]]` — `(AttributeName, AttributeDataType, ModelName)` for non-JSON attributes.

- [ ] **Step 1: Write the failing tests**

Append to `orm/eyened_orm/tests/test_search_repository.py`:

```python
def test_tag_names_lists_linked_tags_sorted(repo, session, data):
    """tag_names returns the distinct tag names reachable through a link table."""
    from eyened_orm import ImageInstanceTagLink

    assert repo.tag_names(session, ImageInstanceTagLink) == ["img-tag"]


def test_active_form_creator_names_excludes_inactive_annotations(repo, session, data):
    """Only creators with a live form annotation are listed."""
    assert repo.active_form_creator_names(session) == ["form-creator"]


def test_attribute_signature_rows_carry_name_dtype_and_model(repo, session, data):
    """Attribute rows describe (name, dtype, producing model) and skip JSON attributes."""
    from eyened_orm.attributes import AttributeDataType

    assert repo.attribute_signature_rows(session) == [
        ("Quality", AttributeDataType.Int, "M1")
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `dev/.venv/bin/python -m pytest orm/eyened_orm/tests/test_search_repository.py -k "tag_names or form_creator_names or attribute_signature_rows" -v -p no:warnings`
Expected: FAIL with `AttributeError: 'SearchRepository' object has no attribute 'tag_names'`

- [ ] **Step 3: Add the repository methods**

In `orm/eyened_orm/repositories/search/repository.py`, extend the imports — replace:

```python
from eyened_orm import ImageInstance, Series, Study
from eyened_orm.attributes import AttributeDefinition
from sqlalchemy import func, select
from sqlalchemy.orm import Session
```

with:

```python
from eyened_orm import Creator, FormAnnotation, ImageInstance, Series, Study, Tag
from eyened_orm.attributes import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModel,
    AttributesModelOutput,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session
```

Add `Optional`/`Tuple` to the typing import — replace:

```python
from typing import Any, List, Literal
```

with:

```python
from typing import Any, List, Literal, Optional, Tuple
```

Then append these methods to `SearchRepository`:

```python
    def tag_names(self, session: Session, link_table: Any) -> List[str]:
        """Distinct tag names reachable through the given tag link table, sorted."""
        return sorted(
            session.scalars(
                select(Tag.TagName)
                .join(link_table, link_table.TagID == Tag.TagID)
                .distinct()
            ).all()
        )

    def active_form_creator_names(self, session: Session) -> List[str]:
        """Names of creators with at least one active form annotation, sorted."""
        return sorted(
            session.scalars(
                select(Creator.CreatorName)
                .join(FormAnnotation, FormAnnotation.CreatorID == Creator.CreatorID)
                .where(~FormAnnotation.Inactive)
                .distinct()
            ).all()
        )

    def attribute_signature_rows(
        self, session: Session
    ) -> List[Tuple[str, AttributeDataType, Optional[str]]]:
        """(AttributeName, AttributeDataType, ModelName) for every non-JSON attribute.

        Model-less attributes carry ModelName None; an attribute produced by several
        models yields one row per model, exactly as the signature endpoint expects.
        """
        stmt = (
            select(
                AttributeDefinition.AttributeName,
                AttributeDefinition.AttributeDataType,
                AttributesModel.ModelName,
            )
            .select_from(AttributeDefinition)
            .outerjoin(
                AttributesModelOutput,
                AttributeDefinition.AttributeID == AttributesModelOutput.AttributeID,
            )
            .outerjoin(
                AttributesModel,
                AttributesModelOutput.ModelID == AttributesModel.ModelID,
            )
            .where(AttributeDefinition.AttributeDataType != AttributeDataType.JSON)
            .distinct()
        )
        return [tuple(row) for row in session.execute(stmt).all()]
```

- [ ] **Step 4: Rewrite the service's signature methods**

In `server/services/search/search_service.py`, replace everything from the module docstring down to and including the `from .fields import (...)` block — i.e. the entire header above `@dataclass class InstanceSearchResult` — with the following. (Line numbers have drifted since Tasks 3 and 5; anchor on the content, not the numbers.)

```python
"""Search orchestration: the RBAC seam.

Read-only: no ActingUser, no audit logger, no commit(). Takes explicit keyword
arguments rather than the route's Pydantic ``SearchQuery`` -- importing that
would invert the routes -> services dependency arrow. ``SearchQuery.model_dump()``
unpacks to exactly this signature. DTO conversion stays behind in the route; this
layer returns ORM rows.

No ``select()`` is built here: query construction belongs to ``SearchRepository``.
Calls to the ``Model.query_column`` ORM helper are the one exception -- they are an
established codebase pattern for enumerating a reference column, not query
construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from eyened_orm import (
    Creator,
    DeviceModel,
    Feature,
    FormAnnotationTagLink,
    FormSchema,
    ImageInstance,
    ImageInstanceTagLink,
    Project,
    SegmentationTagLink,
    Study,
    StudyTagLink,
)
from eyened_orm.attributes import AttributeDataType
from eyened_orm.image_instance import ETDRSField as ImgETDRS
from eyened_orm.image_instance import Laterality as ImgLaterality
from eyened_orm.image_instance import Modality as ImgModality
from eyened_orm.patient import SexEnum as PatientSex
from eyened_orm.repositories.search import SearchRepository
from sqlalchemy.orm import Session

from ..exceptions import BadRequestError
from .conditions import translate_instance_conditions, translate_study_conditions
from .fields import (
    SignatureField,
    instance_order_by_fields_map,
    study_order_by_fields_map,
)
```

Delete the module-level `_query_tag_names` helper entirely (lines 73-79):

```python
def _query_tag_names(session: Session, link_table: Any) -> List[str]:
    """Helper to query distinct tag names from a link table."""
    return sorted(
        session.scalars(
            select(Tag.TagName).join(link_table, link_table.TagID == Tag.TagID).distinct()
        ).all()
    )
```

Replace `instance_signature` with:

```python
    def instance_signature(self, session: Session) -> List[SignatureField]:
        """Return signature metadata for instance search fields."""
        creator_names = sorted(
            Creator.query_column(session, Creator.CreatorName, where=(Creator.IsHuman == True))
        )
        items: list[SignatureField] = [
            # Enum-backed
            SignatureField(name="Laterality", values=[e.value for e in ImgLaterality], nullable=True),
            SignatureField(name="Modality", values=[e.value for e in ImgModality], nullable=True),
            SignatureField(name="ETDRS Field", values=[e.value for e in ImgETDRS], nullable=True),
            SignatureField(name="Patient Sex", values=[e.value for e in PatientSex], nullable=True),
            # DB-derived simple columns
            SignatureField(name="Project Name", values=sorted(Project.query_column(session, Project.ProjectName))),
            SignatureField(
                name="Device Model ID",
                values=[str(v) for v in sorted(DeviceModel.query_column(session, DeviceModel.DeviceModelID))],
            ),
            SignatureField(
                name="Segmentation Feature Name",
                values=sorted(Feature.query_column(session, Feature.FeatureName)),
            ),
            SignatureField(
                name="Segmentation Creator Name",
                values=creator_names,
            ),
            SignatureField(
                name="Segmentation Tag Name",
                values=self.repository.tag_names(session, SegmentationTagLink),
            ),
            SignatureField(
                name="Form Schema Name",
                values=sorted(FormSchema.query_column(session, FormSchema.SchemaName)),
            ),
            SignatureField(
                name="Form Creator Name",
                values=creator_names,
            ),
            SignatureField(
                name="Form Tag Name",
                values=self.repository.tag_names(session, FormAnnotationTagLink),
            ),
            SignatureField(
                name="Image Tag Name",
                values=self.repository.tag_names(session, ImageInstanceTagLink),
            ),
        ]

        # Convert attribute rows to SignatureFields
        dtype_map = {
            AttributeDataType.String: "string",
            AttributeDataType.Int: "int",
            AttributeDataType.Float: "float",
        }
        for name, dtype, model_name in self.repository.attribute_signature_rows(session):
            items.append(
                SignatureField(
                    name=name,
                    values=dtype_map.get(dtype, "string"),
                    type="attribute",
                    model=model_name,
                )
            )
        # Free-text/number defaults
        items.extend([
            SignatureField(name="Image DBID", values="int"),
            SignatureField(name="Color Fundus Quality", values="float", nullable=True),
            SignatureField(name="Study Date", values="date"),
            SignatureField(name="Patient Identifier", values="string", multi=True),
            SignatureField(name="Patient Birthdate", values="date", nullable=True),
        ])

        return items
```

Replace `study_signature` with:

```python
    def study_signature(self, session: Session) -> List[SignatureField]:
        """Return signature metadata for study search fields.

        NOTE: like ``instance_signature``, this enumerates every project, creator and
        tag in the database -- it does not pass through the ``static_conds`` seam.
        RBAC Step 2 must filter here too; the characterization tests pin today's
        cross-project behavior.
        """
        items: list[SignatureField] = [
            # Enum-backed
            SignatureField(
                name="Patient Sex", values=[e.value for e in PatientSex], nullable=True
            ),
            # DB-derived
            SignatureField(
                name="Project Name",
                values=sorted(Project.query_column(session, Project.ProjectName)),
            ),
            SignatureField(
                name="Form Schema Name",
                values=sorted(FormSchema.query_column(session, FormSchema.SchemaName)),
            ),
            SignatureField(
                name="Form Creator Name",
                values=self.repository.active_form_creator_names(session),
            ),
            SignatureField(
                name="Form Tag Name",
                values=self.repository.tag_names(session, FormAnnotationTagLink),
            ),
            SignatureField(
                name="Study Tag Name",
                values=self.repository.tag_names(session, StudyTagLink),
            ),
            # Typed free-entry fields
            SignatureField(name="Study Date", values="date"),
            SignatureField(name="Study Description", values="string", nullable=True),
            SignatureField(name="Study Round", values="int", nullable=True),
            SignatureField(name="Study Instance UID", values="string"),
            SignatureField(name="Patient Identifier", values="string", multi=True),
            SignatureField(name="Patient Birthdate", values="date", nullable=True),
        ]
        return items
```

- [ ] **Step 5: Verify the layering line actually holds**

Run:

```bash
grep -n "select(\|selectinload\|session.execute\|session.scalars" server/services/search/search_service.py
```

Expected: **no output**. If anything matches, a query is still being built or executed in the service and the task is not done.

- [ ] **Step 6: Run the tests and make sure they pass**

Run: `dev/.venv/bin/python -m pytest -q -p no:warnings`
Expected: `365 passed` — the signature characterization tests (`test_routes_search_signature.py`, including `test_study_signature_advertises_a_field_that_cannot_be_searched`) green **unmodified**, proving both signature payloads are byte-identical.

- [ ] **Step 7: Commit**

```bash
git add orm/eyened_orm/repositories/search/repository.py orm/eyened_orm/tests/test_search_repository.py server/services/search/search_service.py
git commit -m "$(cat <<'EOF'
refactor(search): move signature query construction into the repository

SearchService still hand-built ~8 selects, and study_signature re-implemented
_query_tag_names twice while the helper sat at the top of the same file. Both
queries move onto SearchRepository (tag_names, active_form_creator_names,
attribute_signature_rows); the SignatureField assembly stays in the service,
which is vocabulary, not data access.

The line drawn: no select() in server/services/search/ -- enforceable by grep.
Model.query_column calls stay; they are an existing ORM helper, not query
construction.

The signature endpoints still enumerate cross-project values without passing
through the RBAC seam. This does not fix that (Step 2 work, pinned by the
characterization tests) -- it puts the queries where a Step 2 filter can reach.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Scope the `client` fixture's teardown

Finding 8. The fixture calls `app_api.dependency_overrides.clear()` on a module-level singleton, wiping every override rather than the two it installed. Harmless today because it is the only fixture touching `app_api` — a landmine the moment an RBAC Step 2 test composes `client` with its own `get_current_user` override, because the failure would surface in whichever test ran next, not the one at fault.

**Files:**
- Modify: `server/tests/conftest.py:26-51`

**Interfaces:**
- Consumes: nothing.
- Produces: the `client` fixture is unchanged in signature and behavior; only teardown narrows.

**No test for this task, deliberately.** A fixture's teardown runs *after* the body of any test that depends on it, so a test using `client` cannot observe its own teardown. The two ways to fake it are both worse than nothing: asserting inside the test body proves only that the line above it ran, and reimplementing the fixture inline tests a copy rather than the code. Testing it honestly needs pytest's `pytester` to run a nested session — disproportionate for a two-line change to a fixture every other test already exercises. The change is verified by inspection plus the full suite staying green (which proves the narrowed teardown still cleans up what it installed).

- [ ] **Step 1: Narrow the teardown**

In `server/tests/conftest.py`, replace:

```python
    with TestClient(app_api) as c:
        yield c
    app_api.dependency_overrides.clear()
```

with:

```python
    with TestClient(app_api) as c:
        yield c
    # Pop only what this fixture installed: app_api is a module-level singleton, so
    # clear() would silently delete overrides another fixture or test owns.
    app_api.dependency_overrides.pop(get_db, None)
    app_api.dependency_overrides.pop(get_current_user, None)
```

- [ ] **Step 2: Run the tests and make sure they pass**

Run: `dev/.venv/bin/python -m pytest -q -p no:warnings`
Expected: `365 passed` — every route test still goes through this fixture, so a teardown that failed to clean up would surface here as cross-test contamination.

- [ ] **Step 3: Commit**

```bash
git add server/tests/conftest.py
git commit -m "$(cat <<'EOF'
test(search): scope the client fixture teardown to its own overrides

app_api is a module-level singleton and the fixture cleared the whole
dependency_overrides map. Harmless while it is the only fixture touching
app_api, but an RBAC Step 2 test composing client with its own get_current_user
override would have it silently deleted at teardown, failing a later test rather
than the one at fault. Pop the two keys the fixture installed.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Refresh the knowledge graph and update the PR

**Files:**
- Modify: `graphify-out/` (regenerated; untracked — verify before committing anything here)

**Interfaces:**
- Consumes: all prior tasks complete and green.
- Produces: nothing code-facing.

- [ ] **Step 1: Full green run**

Run: `dev/.venv/bin/python -m pytest -q -p no:warnings`
Expected: `365 passed`

- [ ] **Step 2: Confirm the diff is only what these tasks touched**

Run: `git diff origin/development...HEAD --stat`
Expected: the original 22 files plus this plan — 23 files. No client/, no migrations, no unrelated routes.

- [ ] **Step 3: Refresh the graph (repo CLAUDE.md rule)**

Run: `dev/.venv/bin/graphify update .`
Expected: `Rebuilt: <N> nodes, <M> edges`. `graphify-out/` is untracked — do **not** `git add` it unless `git status` shows the repo intends to track it.

- [ ] **Step 4: Push and update the PR description**

```bash
git push origin feature/rbac-step1-service-layer
```

Then edit PR #165's description: add a "Review fixes" section recording the two 500s fixed (multi-version model names; `IN` with a scalar), the resolve-once change (3 round-trips -> 1), and the layering completion (no `select()` in `server/services/search/`). Correct the "Follow-up" section: the signature endpoints' cross-project enumeration is now reachable from `SearchRepository`, which is where Step 2 filters it.

- [ ] **Step 5: Commit any doc changes**

```bash
git add docs/superpowers/plans/2026-07-17-search-review-fixes.md
git commit -m "$(cat <<'EOF'
docs(search): add the review-fix plan executed by these commits

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
git push origin feature/rbac-step1-service-layer
```

---

## Task / Finding Coverage

| Finding | Task |
|---|---|
| 1. Multi-version model name 500s attribute search | 1 |
| 2. `IN` + scalar 500 | 2 |
| 3. Attribute defs resolved 3x, was 1x | 3 |
| 4. Dead re-exports + false noqa comment | 4 |
| 5. `_studies_for` duplicates `study_options()` | 5 |
| 6. Service builds/executes SQL, bypassing the seam | 5, 6 |
| 7. `study_signature` re-implements `_query_tag_names` | 6 |
| 8. `client` fixture clears all overrides | 7 |

## Expected Test Count Progression

| After task | Total |
|---|---|
| baseline | 354 |
| 1 | 355 |
| 2 | 359 |
| 3 | 360 |
| 4 | 360 |
| 5 | 362 |
| 6 | 365 |
| 7 | 365 (inspection-verified, no new test — see Task 7) |
