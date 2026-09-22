# Documentation claims that are wrong against the code

- **Source:** Diátaxis triage of the whole corpus, 2026-09-21. Every item below was verified
  against source in the `feature/deploy-consolidation` worktree; file:line is given on both sides
  so nobody re-derives. Scoped out of the `deploy/` documentation consolidation.

**Status:** open

## What

### Breaks a reader's work

- **`client/panels/etdrs.mdx:31`** — "**right click** to set the **optic disc edge**". Right click
  **deletes** the point under the cursor (`client/src/lib/viewer/tools/PointTool.svelte.ts:307+`,
  `event.button === 2` → `findHit` → `deletePointAt`). Left click fills whichever *slot is armed*
  (`slotLabels: ["Fovea", "Disc edge"]`), armed by the UI or the `f`/`d` keys, which are documented
  nowhere. A grader following the page deletes the point they just placed. **The identical error
  ships in-app** at `client/src/lib/viewer-window/panelHelp/EtdrsPanelHelp.svelte:31-32` — this fix
  is one sentence in two places, one of them code.
- **`orm/data_model/attributes.mdx:96`** — gives `**CLI slug:** etdrs-area`. That string appears
  **nowhere** in `orm/` (grep: zero hits). The real attribute name is `"ETDRS area"` — two words,
  a space — at `orm/eyened_orm/reports/etdrs_model.py:16`, written via `{"AttributeName": …}` at
  `:90`. The producing command is `eorm run-etdrs-model`, which has no slug option at all. On the
  page whose stated purpose (`:42`) is that consumers "read them by exact name".
- **`orm/inference.mdx:27` and `orm/cli.mdx:119`** — `run-cfi-models` with no target flags claims a
  full-database scan. `orm/eyened_orm/commands/model_processing.py:240-243` defaults `modality` to
  `ColorFundus`. OCT and AF images are silently skipped with no message.
- **`api/tasks.mdx:16`** — `POST /api/task` body omits the required `projects`
  (`server/dtos/dtos_tasks.py:44`, `Field(min_length=1)`). Every request built from the page is a
  422. `guides/access_control.mdx:62` documents it correctly, so the section contradicts itself.
- **`api/segmentations.mdx:8-12`** — `POST /api/segmentations` documented as a JSON body; it is
  `multipart/form-data` with `metadata` as a JSON-encoded **string** field plus an optional
  `np_array` upload (`server/routes/segmentations.py:63-72`).
- **`api/import.mdx:14-20`** — a failed import returns `ImportResponse(success=False)` at **HTTP
  200** (`server/routes/import_api.py:158-180`). The page never names the response. An integrator
  checking `response.ok` records failed imports as successes. The endpoint is also admin-only
  (`:128`), which the page does not say.
- **`api/search.mdx:12`** — `order_by` has no default and is therefore required
  (`server/routes/search.py:57`); `include_count` (`:59`) is undocumented.

### Structurally broken

- **`orm/data_model/attributes.mdx:84`** — the `#### Registration` heading is gone. The block now
  reads as a continuation of `CFI_Quality`, making a **Float** attribute look like JSON, and it is
  absent from the page's table of contents.
- **`api/index.mdx:10` contradicts `api/reference.mdx:10`** on whether 403 occurs.
  `server/services/exceptions.py:71-74` (`NotVisibleError: 404, PermissionDeniedError: 403`) and
  `guides/access_control.mdx:49-52` confirm `reference.mdx` is right.

### Numbers that are not what they claim

- **`platform_design.mdx:66`** — Argon2 "64 MiB and roughly 75 ms per hash". No `memory_cost`,
  `time_cost` or `parallelism` is set anywhere in `server/` or `orm/` (grep: zero hits); these are
  passlib defaults described in prose. The `~256 MiB` / `~1 GiB` ceilings at `:68` are derived from
  an unenforced number.
- **`platform_design.mdx:48`** — "Six endpoints deliberately stay on the loop" does not account for
  `server/routes/form_annotations.py:106` (`PUT /form-annotations/{id}/value`).
- **`client/index.mdx:22-24`** — marks Measure, Form and Segmentation "Always" available.
  `client/src/lib/viewer-window/resolvePanels.ts:145-146` removes any panel named in
  `taskConfig.layout.hide` — a mechanism `client/panels/form.mdx:29-38` documents on the next page.
  ETDRS and Registration also require `input.etdrsSchema` / `input.registrationSchema` (`:73`, `:83`).
- **`orm/development.mdx:36` and `orm/README.md:19`** — name `from_imagesets`; the method is
  `create_from_imagesets` (`orm/eyened_orm/task.py:157`). It is the worked example for the
  `from_`-prefix convention, so the one illustration of the rule is the one case that breaks it.

### Smaller

`orm/form_schemas.mdx:38-41` sends a new deployer to `create-user`, which `orm/cli.mdx:56`
documents as producing an account that can log in and see nothing — the first account must be
`init-admin`. `client/panels/registration.mdx:35` says "press 0-9"; `0` is a no-op
(`PointTool.svelte.ts:234-250`). `client/panels/form.mdx:44` says a "Grade" button; the label is
"Open grading" once an annotation exists (`PanelQuickForm.svelte:79`). `README.md:32-33` lists
`client` as a deploy-stack service; production has no client container. `client/index.mdx:8` says
WebGL, `platform_design.mdx:24` says WebGL2. `orm/data_model/attributes.mdx` omits that `ValueText`
is `VARCHAR(255)`.

## Why

These are not stylistic. Six of them cause a reader to write code or run a command that fails, and
one of them causes a grader to destroy their own input while following the instructions.

The pattern worth acting on: **the generated artefacts are right and the hand-written prose drifts.**
`client/src/types/openapi.json` is 79/79 in sync with the server; all 79 routes are documented and
there are no ghost endpoints. Every ORM claim about class names, signatures, enums and config
defaults checked out. The wrong claims cluster in hand-transcribed CLI option tables and
hand-maintained API prose. Generating `orm/cli.mdx`'s option tables from Click would close six of
the ORM findings at once and stop them recurring.
