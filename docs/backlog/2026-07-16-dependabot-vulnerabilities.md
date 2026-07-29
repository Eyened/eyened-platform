# Follow-up: Dependabot vulnerability alerts

- **Source:** Surfaced on push during #118 CI work, 2026-07-16 — GitHub reported
  **82 open Dependabot alerts** on the `development` (default) branch. Detail pulled
  via `gh api /repos/Eyened/eyened-platform/dependabot/alerts`.

**Status:** open

**Pre-existing on `development`, unrelated to #118.** Severities are CVSS scores, not
contextual — real exposure depends on whether each code path is reachable.

## Breakdown (82 total: 28 high / 39 medium / 15 low; 75 npm / 7 pip)

| Location | Count | What it is | Blast radius |
|---|---:|---|---|
| `docs/package-lock.json` | 51 | Astro docs-site toolchain | Lowest — static site generator |
| `client/package-lock.json` | 24 | Frontend (Svelte/Vite) build deps | Mostly build-time |
| `server/requirements.txt` | 7 | Backend runtime (FastAPI) | Highest — request path |

## 1. Backend (pip) — all 7 are `python-multipart`  ← do this first

Pinned at `python-multipart==0.0.20`; **all 7 fixed by ≤ 0.0.31**. FastAPI's form/
multipart parser, reachable on any form or file-upload endpoint.

- HIGH — Arbitrary File Write via non-default config (`<0.0.22`)
- HIGH — DoS via unbounded multipart part headers (`<0.0.27`)
- HIGH — DoS via quadratic querystring parsing with `;` separators (`<0.0.30`)
- MEDIUM — DoS via large multipart preamble/epilogue (`<0.0.26`)
- 3× LOW — parameter smuggling / negative Content-Length buffering (`<0.0.30`/`0.0.31`)

**Fix:** `server/requirements.txt`: `python-multipart==0.0.20` → `>=0.0.31` (verify
current latest). One line, patch-series bump, no API change — clears all 7 including 3 highs.

## 2. Frontend + docs (npm) — 75, mostly tooling

High-severity npm cluster in build/generator tooling, not shipped runtime:
`vite` (4), `tar-fs` (4), `astro` (3), `devalue` (3), plus `rollup`, `@babel/*`,
`picomatch`, `minimatch`, `h3`, `fast-uri`, `simple-git`, `defu`. Many transitive/dev-only.
The 51 in the docs site are lowest concern.

**Fix:** `npm audit fix` sweeps in `client/` and `docs/` as two separate PRs; escalate
to manual major-version bumps only for what `--force` won't safely resolve.

## Recommended sequencing

1. `python-multipart` bump — its own small backend PR (highest value, lowest effort).
2. `npm audit fix` for `client/`, then `docs/` — one PR each.
3. Consider enabling Dependabot version-update PRs so this stops re-accumulating.
