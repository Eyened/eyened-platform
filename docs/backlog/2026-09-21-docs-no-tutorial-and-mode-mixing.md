# The documentation has no tutorial, and most pages carry two or three modes without saying so

- **Source:** Diátaxis triage of the whole corpus, 2026-09-21. Scoped out of the `deploy/`
  documentation consolidation, which holds at three pages by design.

**Status:** open

## What

**There is no tutorial anywhere in the corpus.** Both `getting_started.mdx` files are how-to
(`## Quick Setup`, `## Install`), correctly so. The gap that costs most is the clinician's: a
grader opening `/client` gets a panel index and seven reference pages, and no "open an image,
place a grid, draw a segmentation, save" walkthrough. The ORM's designated tutorial
(`orm/getting_started.mdx`) does not finish either — its closing example (`:81-91`) is not runnable
as written (`session` used outside its `with` block, result never printed), so the only verified
step is `eorm --help`.

**Pages carrying multiple modes without signposting**, worst first:

- `docs/src/content/docs/getting_started.mdx` — all four quadrants: product feature list (`:6-16`),
  tutorial (`:18-68`), reference (`:70-79`, a verbatim duplicate of `deploy/README.md`'s day-to-day
  table), how-to (`:81-105`, `:107-121`), and an ORM install tip for a different audience
  (`:134-158`). The `deploy/` consolidation fixes its factual defects in place and deliberately
  does **not** restructure it; declaring it a tutorial means moving the feature list to
  `index`/`about`, which is this entry's work.
- `thumbnails.mdx` — reference, how-to, API reference, explanation, in that order.
- `release_notes.mdx` — carries **75 lines of ordered outage procedure** (`:233-307`, `:361-367`,
  `:423-431`). Release notes are reference (what changed, scanned); an upgrade is how-to (ordered,
  performed once with the page open). Proposed: an `upgrading/<version>.mdx` section, which is also
  where the stranded runbooks land — see `2026-09-21-docs-publish-boundary-stranded-material.md`.
- `guides/authentication.mdx` — four modes: OIDC how-to (`:16-36`), option reference (`:38-107`),
  explanation (`:110-144`), reference (`:146-161`).
- `orm/form_schemas.mdx` — seeding how-to, `x-eyened-widget` reference, `TaskConfig` reference,
  serving three different readers silently.
- `client/panels/etdrs.mdx` — the only panel page where the declared user/implementation split is
  two real documents; `:56-84` is a deployment prerequisite, a storage table and API field mapping
  that a grader will never read and a data engineer cannot find under a viewer-panel URL.

**No server-settings reference page exists.** The five concurrency defaults are published twice
(`platform_design.mdx:52-58` and `release_notes.mdx:311-321`) and shipped a third time in
`deploy/.env.example`, with no canonical copy. `orm/configuration.mdx` is ORM-scoped by a
deliberate decision (`e5b75a1e`) and contains no `EYENED_API_*`.

**`index.mdx` is an undifferentiated menu.** Six hero actions with no ORM door at all, the
highest-prominence one being "About the project" (funding logos and consortium history), and
"Viewer panels" — the clinician's only entry — demoted to `variant: minimal`. The tagline promises
"import, browse, annotate and export"; there is no annotate destination above the fold and no
export destination anywhere on the page.

**Six of seven panel pages publish author-facing TODOs** (`rendering.mdx:20-22`, `info.mdx:21-23`,
`measure.mdx:20-22`, `form.mdx:48-50`, `registration.mdx:37-39`, `segmentation.mdx:41-43`), four of
which name Svelte source files at the reader. `segmentation.mdx:42` tells the reader the in-app
help is "the most complete reference today". Editorial intent belongs in this file, not on the site.

**Almost nothing declares its reader.** `orm/development.mdx:8` is the only page in the corpus that
names its audience in a sentence. It is the model; nothing else follows it.

## Why

The content is good — `guides/access_control.mdx` is genuine explanation, and the ORM section's
hard-won domain knowledge (why version ordering cannot be lexicographic, why Secondary Capture is
the honest SOP class, why offline DDL generation must not be "fixed") is the expensive part of
documentation and is already paid for. What is missing is the cheap part: mode discipline and a
declared reader per page.

Cost profile, so this can be scheduled honestly: the publish-boundary work is moves and deletions
with no new writing. **This entry is the opposite** — the clinician tutorial and the panel pages
need someone to sit down with the viewer and write, and no amount of triage substitutes for it.
