# Registration model versioning and patient attrs API

## Summary

This PR fixes registration cursor linking in the viewer, allows multiple versions of the same model in the database, and reshapes how patient-level attributes are exposed via the API.

### Registration PublicID and viewer linking

- ORM writes `PublicID` keys in registration JSON (not numeric `ImageInstanceID`), matching the viewer's `image_id`.
- Legacy numeric keys are normalized on read in the API converter and during incremental registration runs.
- Frontend merges registration edges from all model versions and recomputes transitive paths (A→B + B→C links A↔C).

### Model versioning

- Removed the `ModelName`-only unique constraint from the ORM; kept `(ModelName, Version)`.
- Alembic migration drops the legacy `ModelName` unique index on MySQL (autogenerate does not detect this reliably).
- `run-registration` logic (in `registration.py`):
  - Creates a new `Model` row per package version.
  - Seeds the skip graph from **all** prior Registration `AttributeValue`s (any model version), unless `--replace`.
  - Stores **only newly computed edges** in the current model's `AttributeValue`.

### Patient attrs API change

`GET /patients/{id}` now returns:

```json
{
  "attrs": {
    "Registration": [
      {
        "value": [{ "image1": "…", "image2": "…", "transform": { … } }],
        "model": { "id": 1, "name": "retinalysis-registration", "version": "0.1.5" }
      }
    ]
  }
}
```

Each attribute name maps to a **list** of `{ value, model }` entries so provenance per model version is preserved.

### Other

- Aligned `ImageStorage` ORM index name with the live DB (`StorageBackendID_ObjectKey`) to avoid spurious Alembic diffs.
- Fixed stale `openapi_types.ts` exports (`ImageGET`, `ImportRow`).

## Migration

```bash
cd orm/migrations && alembic upgrade head
```

Applies `2026_06_30-fix_model_unique_constraints` (drops `UNIQUE(ModelName)` on `Model`).

## Test plan

- [ ] `pytest orm/eyened_orm/utils/test_registration.py`
- [ ] Apply migration; confirm `SHOW INDEX FROM Model` has no `ModelName`-only unique index
- [ ] Run registration with a bumped `retinalysis-registration` version on a patient that already has registration — no duplicate-key error; seed graph non-zero; only new pairs stored in new `AttributeValue`
- [ ] `make gen-types` — client typechecks
- [ ] Open viewer with registered images from same patient — crosshair sync works
- [ ] `GET /patients/{id}` — `attrs.Registration` is a list of `{ value, model }`

## Out of scope

Unified eORM CLI targeting (#129) is **not** included in this PR — that work remains local on the branch.
