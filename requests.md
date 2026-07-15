# CFI model inference — requirements & UX

Addresses [issue #150](https://github.com/Eyened/eyened-platform/issues/150). That issue describes the original `eorm run-models` workflow (driven by `ImageInstance.DatePreprocessed`) and asks to restore it. This PR keeps the same **end-user goals** but implements state and versioning differently:

| Issue #150 (legacy) | This PR |
|---|---|
| `DatePreprocessed = None` → run preprocessing | No `AttributeValue` row yet for that model → run |
| `DatePreprocessed` set on success/failure | Per-model `AttributeValue` rows record success (non-null value) or failure (null value columns) |
| Re-run everything by clearing `DatePreprocessed` | `--overwrite` or `--upgrade` |
| Implicit / date-based model identity | Explicit `AttributesModel.Version` from installed package or HuggingFace artifact id |

`DatePreprocessed` is **not** used as pipeline state anymore. Dates are a poor proxy for model identity; version strings are derived from the actual code/weights in use.

---

## End-user requirements

These are the behaviors `eorm run-cfi-models` must provide.

### Core workflows

1. **Process new images** — Run with no extra flags; each model automatically picks up images that have no result yet (for that model).
2. **Re-run after a model update** — Run only images that lack the *current* model version (`--upgrade`), or force a full recompute (`--overwrite`).
3. **Re-run a subset** — Scope by project, patient, modality, or an ID list; optionally exclude IDs.
4. **Track failed preprocessing** — A failed ROI (or other model) is recorded in the database and skipped on the next default run; use `--failed` to retry failures within a target, or `--overwrite` to force recompute.
5. **Reuse intermediate results** — When running the full CFI pipeline, `cfi-roi` runs first; dependent models (`cfi-keypoints`, `cfi-odfd`, `cfi-quality`) crop from the stored `CFI_ROI` attribute instead of re-extracting bounds.
6. **Work on real image data** — Load pixels the same way as the rest of the ORM (DICOM and other modalities via `ImageInstance.pixel_array` / data-access adapter, API or disk per `.env`).
7. **Transparent versioning** — Users normally just run the latest code; the platform stores explicit versions internally and resolves the newest available result when reading attributes.
8. **Documented attribute names** — Platform conventions (`CFI_ROI`, `CFI_Keypoints`, `CFI_ODFD`, `CFI_Quality`, …) are stable, queryable `AttributeDefinition` names with model provenance.

### Non-goals (this PR)

- **Worker queue is additive** — `eorm run-cfi-models` remains the primary batch path. Workers (docker compose in `worker/`) are a demo/future async path, not a replacement.
- **ETDRS / segmentation pipelines** — Same input-reuse pattern applies elsewhere (e.g. ETDRS uses segmentation + keypoints), but are out of scope for this command’s docs.

---

## CLI

### Default — new images only

```bash
# All active images in the DB; each model processes only images without a recorded result
eorm run-cfi-models

# Same, scoped to one study and modality
eorm run-cfi-models --project "AMD-Study" --modality ColorFundus
```

### Re-run

```bash
# Recompute current model version even when a result already exists
eorm run-cfi-models --overwrite

# After upgrading weights: run current version only where that version has no row yet
eorm run-cfi-models --upgrade

# Single model, explicit ID list
eorm run-cfi-models --model cfi-keypoints --path image_ids.txt
```

`run-models` remains a deprecated alias for `run-cfi-models`.

### One-time migration (existing databases)

```bash
eorm migrate-cfi-model-versions
```

Idempotent: renames legacy `AttributesModel.Version` strings (e.g. date-like labels) to the canonical ids used by the current pipeline code.

---

## ORM / notebook

```python
from eyened_orm import Database, ImageInstance
from eyened_orm.commands.model_processing import run_cfi_attribute_pipeline
from eyened_orm.inference.utils import auto_device
import torch

session = Database().create_session()
image_ids = [331115]

# Same logic as the CLI — one model slug
run_cfi_attribute_pipeline(
    session,
    image_ids,
    "cfi-roi",
    device=auto_device(),
    overwrite=False,
    upgrade=False,
)
session.commit()

# Read results (always picks highest-version *successful* value)
im = ImageInstance.by_id(session, image_ids[0])
print(im.roi)                    # CFI_ROI dict
print(im.get_attribute_value(attribute_name="CFI_Keypoints"))

# Inspect provenance: which inputs produced an output
for av in im.AttributeValues:
    print(av.AttributeDefinition.AttributeName, av.ProducingModel.Version, av.value)
    for inp in av.InputValues:
        print("  input:", inp.AttributeDefinition.AttributeName, inp.ProducingModel.Version)
```

---

## How each requirement is fulfilled

### 1. Run on all unprocessed images

**What you do:** `eorm run-cfi-models` (optionally with `--project` / `--modality`).

**What happens:** The command resolves a target (default: all active images). Each model skips images that already have a succeeded or failed `AttributeValue` for that attribute/model name. Only *missing* images are processed.

```bash
eorm run-cfi-models --modality ColorFundus
# => "Skipping N images with existing results"
# => "Processing M images (after filtering, default)"
```

### 2. Re-run existing values (`--overwrite`)

**What you do:** Pass `--overwrite`.

```bash
eorm run-cfi-models --overwrite --project "AMD-Study"
```

**What happens:** Filtering is bypassed; every image in the target is reprocessed for the selected model(s).

### 3. Track failed preprocessing state

**What you do:** Run normally; failures are persisted automatically. Retry with `--failed` (within a target) or `--overwrite`.

**What happens:** A failed inference creates an `AttributeValue` row with all value columns `NULL`. The next default run skips that image (same as a success row). Retry failed images only:

```bash
eorm run-cfi-models --project "AMD-Study" --failed
eorm run-cfi-models -m cfi-roi --path ids.txt --failed
```

```python
im = ImageInstance.by_id(session, image_id)
if im.roi is None:
    # Either not run yet, or CFI_ROI failed (see logs / require_available=False lookup)
    ...
```

To inspect failure explicitly:

```python
from eyened_orm.inference.model_inputs import select_attribute_value
from eyened_orm.inference.attribute_value_outcome import attribute_value_outcome, AttributeValueOutcome

failed = select_attribute_value(
    im.AttributeValues,
    attribute_name="CFI_ROI",
    producing_model_name="CFI_ROI",
    require_available=False,
)
if failed and attribute_value_outcome(failed) == AttributeValueOutcome.FAILED:
    print("ROI extraction failed for this image")
```

### 4. Explicit model versions (not dates)

**What you do:** Nothing special — versions are set from installed packages and model artifacts.

| Model | Version source | Example |
|---|---|---|
| `CFI_ROI` | `retinalysis-fundusprep` package version | `1.1.0` |
| `CFI_Keypoints` | HuggingFace artifact paths | `Eyened/vascx/discedge/...` + `Eyened/vascx/fovea/...` |
| `CFI_ODFD`, `CFI_Quality` | HuggingFace artifact path | `Eyened/vascx/odfd/odfd_march25` |

**Upgrade path:**

```bash
eorm migrate-cfi-model-versions   # fix legacy DB rows once
eorm run-cfi-models --upgrade
```

`--upgrade` runs the current pipeline version only on images that do not yet have a row for that version. Older `AttributeValue` rows are kept; reads prefer the newer version.

### 5. Pipeline reuses intermediate output (`CFI_ROI`)

**What you do:** Run all models (default) or ensure `cfi-roi` has run before dependent models.

```bash
eorm run-cfi-models
# Order: cfi-roi → cfi-keypoints → cfi-odfd → cfi-quality
```

**What happens:** `cfi-keypoints`, `cfi-odfd`, and `cfi-quality` declare `CFI_ROI` as a required input. They resolve the highest-version successful `CFI_ROI` attribute and crop from it — they do not call `get_cfi_bounds` again.

In a notebook, provenance is visible on each output:

```
CFI_Keypoints  Eyened/vascx/...  {fovea_xy: [...], disc_edge_xy: [...]}
  => 1393538 CFI_ROI 1.1.0 {...}
```

Other pipelines follow the same pattern (e.g. ETDRS summary consumes segmentation + keypoint attributes).

### 6. DICOM and shared image loading

**What you do:** Run inference on any `ImageInstance` the ORM can load — same as thumbnails, viewer, or import paths.

**What happens:** `CFIAttributeInferencePipeline` loads RGB via `load_fundus_rgb(image)`, which uses `image.pixel_array` and the configured data-access adapter (local disk or API per `.env`).

```python
im = ImageInstance.by_id(session, image_id)
rgb = im.pixel_array   # same entry point as inference
```

### 7. Versioning hidden from day-to-day use

**What you do:** Read attributes with shorthand properties or `get_attribute_value`; no version arguments required.

```python
im.roi                                          # latest successful CFI_ROI
im.get_attribute_value(attribute_name="CFI_Quality")
im.find_attribute_value(producing_model_name="CFI_Keypoints")  # full row + provenance
```

The selector always picks the **highest-version successful** row among candidates.

### 8. Documented platform attribute names

| Attribute | Model slug | Role |
|---|---|---|
| `CFI_ROI` | `cfi-roi` | Fundus bounds / crop transform (JSON) |
| `CFI_Keypoints` | `cfi-keypoints` | Fovea and disc edge coordinates (JSON) |
| `CFI_ODFD` | `cfi-odfd` | Optic disc–fovea distance (Float) |
| `CFI_Quality` | `cfi-quality` | Quality score (Float) |

Legacy `ImageInstance` columns (`CFROI`, `CFKeypoints`, `CFQuality`) remain for backward compatibility but new inference writes `AttributeValue` rows.

### Worker workflow (out of scope, demo only)

```bash
cd worker
docker compose -f docker-compose.cfi-roi.yml up
# API can enqueue the same jobs; workers are optional infrastructure
```

---

## Bug fixes

- **DICOM loading** — Inference uses the ORM `pixel_array` path (including DICOM decode), fixing cases where raw paths failed for `.dcm` images.
- **Consistent data access** — `load_fundus_rgb` goes through `get_data_access_adapter()` like the rest of the platform, so both API-backed and on-disk layouts work depending on environment configuration.

---

## Migration guide

For databases created before explicit versioning:

1. Deploy the updated ORM / pipeline code.
2. Run once:

   ```bash
   eorm migrate-cfi-model-versions
   ```

3. Backfill or upgrade model outputs as needed:

   ```bash
   eorm run-cfi-models                      # missing results only
   eorm run-cfi-models --upgrade   # new version, old rows kept
   eorm run-cfi-models --overwrite        # full recompute
   ```

No manual `DatePreprocessed` reset is required.
