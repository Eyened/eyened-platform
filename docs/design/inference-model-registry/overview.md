# Model inference: where it stands, and where it is going

Branch `feature/inference-model-registry`, commit `1dadceaf`. Compared with the state just before this work (`2c4d94ec`, after `cfi-drusen` was added).

## 1. Direction

**Long term,** only a few critical models should be native to the platform. Specific models, including `cfi-amd` and `cfi-drusen`, should be **add-ons**, and users should be able to add their own. That probably needs four things:

- a **declarative description** of a model: what it is, which inputs it needs, which outputs it produces;
- a **communication interface** that a model implements to talk to the platform;
- at minimum, **processing a single image**;
- optionally, **processing batches**, which is more efficient if the model stays loaded between requests.

**For now,** all models are integrated in the platform. That is deliberate: integrating them side by side is how we learn where each one belongs, and which abstractions the platform needs to provide to integrate models generically.

**This change is mainly maintenance.** It simplifies the existing integration and does not yet build the add-on mechanism. Before, every model carried its own copy of the platform plumbing. Merging those copies gives the first draft of a shared model contract (section 3), and makes the real differences between models visible (section 4). Those differences are what a generic interface has to handle. Section 5 sketches where this could go, and section 7 collects the questions that are still open.

## 2. The models today

| Model | Produces | Today | Suggested future place (to decide) |
|---|---|---|---|
| `cfi-roi` | `CFI_ROI` fundus bounds | integrated, no torch | **native**: thumbnails, cropping and the viewer depend on it |
| `cfi-keypoints` | fovea and disc-edge points | integrated | native or add-on: the ETDRS grid uses it |
| `cfi-odfd` | optic disc–fovea distance | integrated | native or add-on: the ETDRS grid uses it |
| `cfi-quality` | quality score | integrated | add-on |
| `cfi-amd` | drusen, RPD, hyperpigmentation and RPE degeneration maps | integrated, own worker image | **add-on** |
| `cfi-drusen` | drusen map | integrated, no worker image yet | **add-on** |
| `layer-segmentation` | OCT layers | integrated, own worker image | add-on |

All of them are listed in [`registry.py`](../../../orm/eyened_orm/inference/registry.py#L45-L76).

## 3. What this change did: a first draft of the model contract

**In one sentence:** before, every model brought its own database code, run loop, CLI command, API route and RQ task. Now a model is a small compute-only class plus one registry line, and one shared runner, CLI command, route and task serve them all.

| | Before | After |
|---|---|---|
| Model files (7 models) | 1,481 lines | 528 lines |
| CLI, routes, tasks, client, post-import | 6 files with per-type branches | −942 / +201 lines |
| Non-test code in `orm/` and `server/` | | −2,785 / +1,305 lines |
| Steps to add a model | pipeline + DB code + CLI + route + task + client method + post-import branch | one `Pipeline` subclass + one `ModelSpec` line |

Each part below is written as what it does now, and what it is a draft of for add-ons.

### 3.1 The model is pure compute: `Pipeline`

[`pipeline.py`](../../../orm/eyened_orm/inference/pipeline.py#L39-L81)

**Now.** A model declares:

- `output`: where its results go;
- `inputs`: the stored attribute values it consumes;
- `image_input`: `"fundus_rgb"` or `"volume"`;
- `needs_torch`.

It implements the hooks it needs: `load`, `preprocess`, `process_batch` and `postprocess`.

It never touches the database. [`predict()`](../../../orm/eyened_orm/inference/pipeline.py#L65-L72) runs one image in-process, and `process_batch` runs many with the model kept loaded.

**Before.** There were two unrelated families of model classes:

- attribute models subclassed a 561-line base class that took the database session and mixed model code with selection, saving and commits;
- each segmentation model (`CFI_AMD` with 442 lines, `LayerSegmentation` with 426, `CFI_Drusen` with 257) had its own copy of those parts.

**Draft of:** the two halves of the future interface. `predict` is "process a single image" and `process_batch` is "process a batch". The model only sees pixels and plain input values, which is exactly what an out-of-process add-on would receive.

### 3.2 Outputs are declared: `AttributeOutput` and `SegmentationOutput`

[`outputs.py`](../../../orm/eyened_orm/inference/outputs.py)

**Now.** A model states its output as data. For example:

```python
SegmentationOutput(features=(SegFeature("drusen", "Drusen", "Drusen", "4", ...),))
```

The platform turns that declaration into database rows and a *sink*:

- [`pending`](../../../orm/eyened_orm/inference/outputs.py#L136-L153) picks the images that still need work;
- `save` stores a result;
- `save_failure` records a failed image.

Every model gets the same rules:

- the four modes (`default`, `upgrade`, `failed`, `overwrite`);
- a failure never overwrites an earlier success;
- segmentation dimensions can't change on overwrite;
- masks below the threshold aren't written;
- multi-feature models are re-run until every feature exists.

**Draft of:** the "outputs" half of a declarative model description. Two output kinds cover every model today: attribute values (JSON, floats and so on) and segmentations (2D or 3D, with an optional projection matrix).

### 3.3 Inputs are declared and resolved by the platform

[`model_inputs.py`](../../../orm/eyened_orm/inference/model_inputs.py); resolution happens in [`runner._resolve_inputs`](../../../orm/eyened_orm/inference/runner.py#L60-L78).

**Now.** `inputs = (CFI_ROI_INPUT,)` means the model needs a stored `CFI_ROI`. The runner looks it up, skips images where it is missing or failed, and passes the value to the model as plain data. For attribute outputs it also records which input value was used.

**Draft of:** the "required inputs" half of the description, and dependency ordering between models. [`test_registry.py`](../../../orm/eyened_orm/inference/tests/test_registry.py) checks that every input is produced by an earlier model.

### 3.4 One registry

[`registry.py`](../../../orm/eyened_orm/inference/registry.py#L20-L87)

**Now.** Each `ModelSpec` gives:

- the slug, which is also the CLI value, the API value and the RQ queue name;
- the pipeline, as a lazily imported class;
- the modalities it runs on;
- `batch_size` and `n_workers`;
- `supports_upscale`;
- `seconds_per_image`, which sets the job timeout.

The CLI choices, API types, queue names, timeouts and post-import loop all derive from it. Before, this information was spread over slug constants, a timeout table in `server/main.py`, and per-model branches.

**Draft of:** the deployment half of the description: resources, batching and timeouts. Today it is Python in the platform; for add-ons it would become a manifest the platform discovers.

### 3.5 One runner, one entrypoint per surface

[`run_model`](../../../orm/eyened_orm/inference/runner.py#L140-L227) is the one place that, for every model:

1. filters images by modality;
2. selects the pending images;
3. resolves inputs;
4. streams images through [`MultiProcessInference`](../../../orm/eyened_orm/inference/multi_process_inference.py#L140-L215), either with workers or in-process (`n_workers=0`);
5. commits in batches, retrying the whole batch on a MySQL deadlock;
6. fails the job when images failed without a recorded failure.

It is reached through:

| Surface | Before | After |
|---|---|---|
| CLI | `run-cfi-models`, `run-segmentation` (different flags) | [`run-model`](../../../orm/eyened_orm/commands/model_processing.py#L154-L171); `run-models` kept as a deprecated alias |
| API | `/import/run_cfi_models`, `/import/run_cfi_amd`, `/import/run_layer_segmentation` | [`/import/run_model`](../../../server/routes/import_api.py#L182-L218) with `models` and `mode` |
| RQ task | three task functions | [`run_model_job`](../../../server/utils/tasks.py#L35-L57) |
| API client | three `enqueue_*` methods | [`enqueue_run_model`](../../../orm/eyened_orm/api_client.py#L84-L110) |
| Post-import | per-type helpers | [a loop over `MODELS`](../../../orm/eyened_orm/importer/postimport.py#L94-L110) |

**Draft of:** the platform side of the interface. Whatever the transport turns out to be, selection, inputs, persistence, provenance and retries stay in the platform, and a model adds no new surfaces.

**This breaks callers on purpose.** Scripts using the old routes or client methods must switch, and the API now takes `mode` instead of an `overwrite` flag. The [release notes](../../src/content/docs/release_notes.mdx) say so.

## 4. What the integrated models teach us

These are the differences that remain once the plumbing is shared. A generic interface has to account for each of them.

### 4.1 Models bring their own preprocessing, and it isn't consistent

Every CFI model first finds the *fundus bounds* (the centre and radius of the retina circle), then crops that circle to a fixed size. The bounds always come from `get_cfi_bounds(image)` in `retinalysis-fundusprep`. That function is deterministic for the same pixels and package version, and falls back to the full frame, so in practice it never fails.

A model either **computes** the bounds fresh from the pixels, or uses the **stored** `CFI_ROI` that `cfi-roi` wrote earlier with the same function. Pixel decoding is the same for all models ([`Pipeline.load_image`](../../../orm/eyened_orm/inference/pipeline.py#L58-L63)).

**Why the projection matrix is crucial.** In native mode, segmentation models store their maps in the 1024×1024 crop, together with an `ImageProjectionMatrix` that maps the crop back to the photo; the viewer uses it to overlay the map. The matrix is only correct if it comes from the same bounds as the crop. Otherwise the map is overlaid shifted or scaled, and nothing reports an error. Upscale mode warps the map back with the crop's own transform and stores no matrix.

| Model | Needs `CFI_ROI` | Bounds for the crop | Bounds for the stored geometry | Model input | Without a usable `CFI_ROI` |
|---|---|---|---|---|---|
| `cfi-keypoints` | yes | stored | stored (points mapped back) | 512, RGB + contrast-enhanced, ImageNet-normalised | skipped |
| `cfi-odfd` | yes | stored | stored (distance mapped back) | 512, RGB, ImageNet-normalised | skipped |
| `cfi-quality` | yes | stored | — (a score) | 224, RGB, ImageNet-normalised | skipped |
| `cfi-amd` native | yes | **computed** | **stored** (matrix from `CFI_ROI`) | 1024, RGB + 2× contrast-enhanced, /255 | skipped |
| `cfi-amd` upscale | no | computed | computed (map warped back) | as native | runs |
| `cfi-drusen` native | no | computed | computed (matrix from the same bounds) | 1024 view on a 1280 canvas, RGB + contrast-enhanced, /255 | runs |
| `cfi-drusen` upscale | no | computed | computed (map warped back) | as native | runs |

"Without a usable `CFI_ROI`" covers both a missing row and a failed row.

Where each model gets its bounds:

- **Attribute models:** [`crop_fundus_from_roi`](../../../orm/eyened_orm/inference/cfi_preprocess.py#L37-L52).
- **`cfi-amd`:** [`CFI_AMD.preprocess`](../../../orm/eyened_orm/inference/cfi_amd_segmentation.py#L80-L86) builds the matrix with [`cfi_roi_projection_matrix`](../../../orm/eyened_orm/inference/cfi_amd_segmentation.py#L18-L27), and gets the crop from the external `cfi_amd.preprocess_image`, which calls `get_cfi_bounds` itself.
- **`cfi-drusen`:** [`CFI_Drusen.process_batch`](../../../orm/eyened_orm/inference/cfi_drusen_segmentation.py#L35-L41) calls the external `Processor` without bounds, so the package computes them and builds both the crop and the matrix from them.

**Native `cfi-amd` uses two sources of bounds.** Its matrix comes from the stored ROI. This is the same value as `ImageInstance.cropping_matrix_inverse`, which the old code read at save time, and a test checks they are equal. Its crop, however, comes from bounds that `cfi_amd.preprocess_image` recomputes.

The two agree only when `cfi-roi` ran on the same pixels with the same fundusprep version. They can diverge when:

- the `cfi-roi` and `cfi-amd` worker images ship different fundusprep versions;
- the stored ROI is from an older `CFI_ROI` version;
- the pixels or the ROI changed in between.

This behaviour predates this change. The refactor only made it visible by putting the matrix and the crop side by side.

**Lesson for add-ons.** External packages like `cfi_amd` and `cfi_drusen` do their own preprocessing internally. The platform has to decide whether geometry such as fundus bounds is:

- something it *provides* to models, as a declared input;
- something models *report back*, with the transform included in the output;
- or both, with a consistency check.

The crop recipe itself (size, channels, normalisation) is fixed by each model's training, and should stay model-specific.

### 4.2 Inputs can depend on the mode

Native `cfi-amd` needs `CFI_ROI`; upscale `cfi-amd` doesn't. Today the instance sets its `inputs` in `__init__` ([`cfi_amd_segmentation.py`](../../../orm/eyened_orm/inference/cfi_amd_segmentation.py#L67-L69)). A static manifest needs a way to express this: either per-mode input lists, or the two modes as separate model variants.

### 4.3 Not every model can run in the shared multi-process engine

- **`cfi-drusen` and `layer-segmentation`** process one image at a time in the parent process (`n_workers=0`):
  - the drusen processor holds its five-fold ensemble;
  - nnU-Net works on temporary directories ([`_segment`](../../../orm/eyened_orm/inference/layer_segmentation.py#L141-L164)).
- **The attribute models and `cfi-amd`** batch on the GPU with preprocessing in worker processes.

So the interface needs "single image" as the baseline, and batching as an optional capability, not an assumption.

### 4.4 Image kinds differ

Fundus models take an RGB `uint8` array; layer segmentation takes a full OCT volume (`image_input = "volume"`), and its output is 3D. An interface that sends "an image" must also handle volumes, and the large outputs they produce.

### 4.5 Deployment is per model, and currently runs with full platform access

Each model has its own worker image (see `deploy/compose.workers.yaml`) with its own torch and CUDA stack. Each image installs the whole platform library and connects directly to the database and storage.

The existing out-of-platform path, [`docker_runner.py`](../../../orm/eyened_orm/inference/docker_runner.py), starts a fresh container per image. That reloads the model weights every time and supports only `cfi-amd` and layer segmentation.

`cfi-drusen` shows the gap: it is registered but has no worker image, so its queued jobs wait.

**Lesson for add-ons:**

- dependency isolation per model is a real requirement;
- an add-on should not need database credentials;
- the model should stay loaded between images.

### 4.6 Failure semantics differ by output kind

Attribute outputs record a failed row, so `--failed` can retry it. Segmentation outputs record nothing: the run saves the rest and then fails the job. The interface needs one way for a model to say "this image failed", and the platform should decide how to record it.

## 5. Towards user-added models: a proposal

This is a sketch to discuss, built from what section 4 showed.

### 5.1 Split of responsibilities

| The platform owns | The model owns |
|---|---|
| choosing images (modalities, modes, pending, inputs present) | turning pixels plus input values into outputs |
| decoding pixels, and resolving and recording inputs | its own weights, dependencies and hardware |
| storing outputs, versions, provenance and failures | its preprocessing recipe (size, channels, normalisation) |
| queues, retries, timeouts, permissions, UI and API | optionally, batching |

`run_model` and `Pipeline` already follow this split in-process. The proposal is to keep the left column in the platform and move the right column behind an interface.

### 5.2 A declarative description (manifest)

The current `ModelSpec` and output declarations, written as data instead of Python:

```yaml
name: cfi-drusen
version: "4"
description: https://github.com/Eyened/amd-features
modalities: [ColorFundus]
image: fundus_rgb            # or: volume
inputs: []                   # e.g. [{attribute: CFI_ROI, model: CFI_ROI}]
outputs:
  - kind: segmentation
    features:
      - {key: drusen, feature: Drusen, model: Drusen}
    representation: probability
    threshold: 0.5
    geometry: crop_with_matrix   # or: original_image
capabilities:
  batch: false
  max_batch_size: 1
resources:
  gpu: true
  seconds_per_image: 30
variants:                     # covers 4.2: mode-dependent inputs and outputs
  upscale: {outputs.geometry: original_image}
```

The platform validates the manifest, registers the outputs (as `outputs.py` does now), orders models by their inputs, and adds the model to the CLI, API and queues.

### 5.3 The communication interface

| Option | What a model implements | Keeps the model loaded | Isolates dependencies | Needs no database access | Fit |
|---|---|---|---|---|---|
| **A. In-process Python plugin** (an entry point that returns a `Pipeline`) | a Python class, as today | yes | no: it shares the worker's Python, torch and CUDA | no | **core models**, which is today's mechanism |
| **B. One-shot container** (as `docker_runner.py`) | a CLI: input file in, output file out | no: weights reload per image | yes | yes | simple, but too slow for large runs |
| **C. Long-running model container with a small HTTP API** | a server with the endpoints below | yes | yes | yes | **suggested for add-ons** |
| D. Model container as an RQ worker | the platform worker library | yes | partly | no | ties add-ons to platform internals |

Suggested: **A for the few native models, C for add-ons.** In option C, a generic platform worker keeps today's runner. Instead of calling a `Pipeline` in-process, it calls the model container:

- `GET /manifest` returns the description from 5.2, so the platform can discover and validate the model;
- `GET /health` reports readiness, for example once the weights are loaded;
- `POST /predict` (**required**) takes one image plus its resolved input values, and returns the outputs or a failure;
- `POST /predict_batch` (**optional**, advertised in `capabilities`) takes several images, so the model can batch on the GPU.

Payloads:

- images and masks as `.npy` or PNG bodies (or a shared-volume path for large OCT volumes);
- input values and attribute outputs as JSON;
- segmentation outputs as arrays, plus the projection matrix when the geometry is `crop_with_matrix`.

Why C fits:

- the model stays loaded;
- each add-on brings its own image and CUDA stack;
- it needs no database or storage credentials;
- it can be written in any language;
- compose can already schedule GPU containers.

The platform side barely changes. A `RemotePipeline` adapter implements `predict` and `process_batch` as HTTP calls, so the runner, outputs, modes and tests stay as they are. Today's in-process `Pipeline` would remain the reference implementation and the test double. The fake models in [`fake_models.py`](../../../orm/eyened_orm/inference/tests/fake_models.py) already exercise the full contract against SQLite.

### 5.4 Adding a model today

Until add-ons exist, adding a model means writing one `Pipeline` subclass and adding one `ModelSpec` line. See [Adding a model](../../src/content/docs/orm/inference.mdx) in the ORM inference docs:

```python
class MyScore(Pipeline):
    output = AttributeOutput(model_name="My_Score", attribute_name="My_Score",
                             data_type=AttributeDataType.Float, version="1")
    inputs = (CFI_ROI_INPUT,)

    def process_batch(self, preps): ...
    def postprocess(self, prep, out): ...
```

```python
ModelSpec("my-score", f"{_PKG}.my_score:MyScore", _CFI),  # in registry.py
```

After that, the model works through the CLI, the API, its own queue, post-import, the skip modes and input tracking.

## 6. Behaviour changes in this branch

- **One entrypoint per surface.** The old CLI commands, routes, tasks and client methods are removed (section 3.5).
- **Native `cfi-amd` declares `CFI_ROI` as an input.** Images without a usable ROI are skipped before inference. Before, they ran through the model and then failed one by one at save time with a printed error. The stored matrix is computed exactly as before (section 4.1).
- **Segmentation failures fail the job** after the rest is saved. Layer segmentation already did this; `cfi-amd` only printed the errors.
- **The mode flags are shared by all models.** `run-segmentation` had `--skip-existing`. Segmentation models now take the same flags as attribute models, and reject `--failed`.
- **The tests were rebuilt around behaviour:**
  - two tiny fake models run end to end against SQLite in [`test_runner.py`](../../../orm/eyened_orm/inference/tests/test_runner.py), covering input tracking, missing inputs, modalities, the four modes, versions, segmentation features, thresholds, dimensions, worker parity, deadlock replay and failure handling;
  - the registry contract, the CLI, the server queueing and the pure model helpers have their own tests;
  - plumbing tests and duplicates were removed;
  - overall, test code went from 1,902 lines removed to 794 added;
  - the full server suite passes without torch, as in CI (1,243 tests), and 87% of changed lines are covered.

## 7. Open questions

- **Core or add-on:** which models are native? `cfi-roi` seems clear. `cfi-keypoints` and `cfi-odfd` depend on whether the ETDRS grid is a core feature.
- **Fundus bounds (4.1):** options to discuss:
  - **A. Every CFI model uses the stored `CFI_ROI`.** AMD would crop with the stored bounds; drusen would pass `bounds=` to its `Processor`, which it already supports.
    - Pros: one source of truth that matches `ImageInstance.cropping_transform`.
    - Cons: every model depends on `cfi-roi` having run.
  - **B. Every model computes its own bounds.**
    - Pros: self-contained, and the crop and matrix always match.
    - Cons: the stored ROI can drift from what the models used.
  - **C. Use the stored ROI if present, otherwise compute it.**
    - Pros: no hard dependency.
    - Cons: two code paths, and the output depends on database state.
  - For add-ons: should the platform provide the bounds or the crop as a declared input, or should models return their transform?
- **Provenance for segmentations:** should a segmentation record which `CFI_ROI` it used? Attribute values link their inputs; `ModelSegmentation` doesn't.
- **Mode-dependent inputs (4.2):** per-mode inputs in the manifest, or separate model variants?
- **Interface (5.3):** is HTTP the right transport, or should add-ons pull work from a queue? How should large OCT volumes and outputs be transferred?
- **Versions:** should `retinalysis-fundusprep` be pinned across worker images while models are integrated?
- **`cfi-drusen` deployment:** add a worker image now, or leave it out of the default set until the add-on mechanism exists? Requests that don't name models currently queue drusen jobs that wait.
- **This PR's scope:** the branch still contains the five `cfi-drusen` commits that aren't in `development`. Merging `feature/cfi-drusen` first shrinks this PR to the refactor alone.
