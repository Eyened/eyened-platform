# Unified eORM targeting (#129) and registration model versioning

## Summary

This PR adds consistent CLI targeting for eORM inference and maintenance commands, and fixes registration model versioning, viewer cursor linking, and patient-level attribute provenance in the API.

### Unified eORM targeting (#129)

New module `orm/eyened_orm/commands/targets.py` with shared `TargetSpec`, resolvers, and Click decorators:

| Flag | Description |
|------|-------------|
| `-p` / `--path` | File with one `ImageInstanceID` or `PublicID` per line |
| `--image-ids` | Comma-separated numeric IDs |
| `--project` | Project ID or name |
| `--patient` | Patient identifier (with `--project` when ambiguous) |
| `--exclude` / `--skip` | IDs or PublicIDs to exclude |
| `--modality` | Filter when expanding `--project` or `--patient` |

**Migrated commands:** `run-models`, `run-segmentation`, `run-registration`, `run-etdrs-model`

**Optional targeting added to:** `update-thumbnails`, `update-hashes` (via `cli.py`)

**Tests:** `orm/eyened_orm/commands/test_targets.py`

**Docs:** Targeting section in `docs/src/content/docs/orm/cli.mdx`

Also bumps `retinalysis-registration` to `>=0.1.6` in `orm/setup.py`.

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
- Added `build/` to `orm/.gitignore`.

## Migration

```bash
cd orm/migrations && alembic upgrade head
```

Applies `2026_06_30-fix_model_unique_constraints` (drops `UNIQUE(ModelName)` on `Model`).

## Test plan

- [ ] `pytest orm/eyened_orm/commands/test_targets.py`
- [ ] `pytest orm/eyened_orm/utils/test_registration.py`
- [ ] Apply migration; confirm `SHOW INDEX FROM Model` has no `ModelName`-only unique index
- [ ] `eorm run-registration --project <name> --patient <id>` — targets resolve by project name
- [ ] `eorm run-registration --skip <PublicID>` — skip works with PublicID
- [ ] Run registration with bumped `retinalysis-registration` on a patient with existing registration — no duplicate-key error; seed graph non-zero; only new pairs in new `AttributeValue`
- [ ] `make gen-types` — client typechecks
- [ ] Open viewer with registered images from same patient — crosshair sync works
- [ ] `GET /patients/{id}` — `attrs.Registration` is a list of `{ value, model }`

Closes #129.
