# Follow-up: Dependabot vulnerability alerts

- **Source:** Surfaced on push during #118 CI work, 2026-07-16 — GitHub reported
  **82 open Dependabot alerts** on the `development` (default) branch. Detail pulled
  via `gh api /repos/Eyened/eyened-platform/dependabot/alerts`. Re-counted
  2026-08-24: **125 open**, so this has been accumulating at roughly one a day.

**Status:** open

**Pre-existing on `development`, unrelated to #118.** Severities are CVSS scores, not
contextual — real exposure depends on whether each code path is reachable.

## Breakdown, re-counted 2026-08-24 (125 total: 57 high / 49 medium / 19 low; 111 npm / 14 pip)

| Location | Count | What it is | Blast radius |
|---|---:|---|---|
| `docs/package-lock.json` | 62 | Astro docs-site toolchain | Lowest — static site generator |
| `client/package-lock.json` | 49 | Frontend (Svelte/Vite) build deps | Mostly build-time |
| `server/requirements.txt` | 7 | Backend runtime (FastAPI) | Highest — request path |
| `server/test-requirements.txt` | 7 | The same pin, seen through `-r requirements.txt` | Test-time |

## 1. Backend (pip) — all 14 are `python-multipart`  ← do this first

Pinned at `python-multipart==0.0.20`; **all fixed by ≤ 0.0.31**. FastAPI's form/
multipart parser, reachable on any form or file-upload endpoint.

The seven advisories are counted twice, because Dependabot began treating
`server/test-requirements.txt` as a fourth manifest on 2026-08-14 (alerts
#222–#228). That file pins nothing itself — it starts `-r requirements.txt` — so
the same one-line bump clears **14 alerts, not 7**.

- HIGH — Arbitrary File Write via non-default config (`<0.0.22`)
- HIGH — DoS via unbounded multipart part headers (`<0.0.27`)
- HIGH — DoS via quadratic querystring parsing with `;` separators (`<0.0.30`)
- MEDIUM — DoS via large multipart preamble/epilogue (`<0.0.26`)
- 3× LOW — parameter smuggling / negative Content-Length buffering (`<0.0.30`/`0.0.31`)

**Fix:** `server/requirements.txt`: `python-multipart==0.0.20` → `>=0.0.31` (verify
current latest). One line, patch-series bump, no API change — clears all 14 including 6 highs.

## 2. Frontend + docs (npm) — 111, mostly tooling

High-severity npm cluster in build/generator tooling, not shipped runtime:
`brace-expansion` (6), `js-yaml` (5), `fast-uri` (5), `vite` (4), `tar-fs` (4),
`postcss` (4), `nanoid` (4), `astro` (3), `devalue` (3), plus `rollup`, `@babel/*`,
`picomatch`, `minimatch`, `h3`, `immutable`, `undici`, `sharp`, `simple-git`, `defu`.
Many transitive/dev-only. The 62 in the docs site are lowest concern.

**Fix:** `npm audit fix` sweeps in `client/` and `docs/` as two separate PRs; escalate
to manual major-version bumps only for what `--force` won't safely resolve.

## Recommended sequencing

1. `python-multipart` bump — its own small backend PR (highest value, lowest effort).
2. `npm audit fix` for `client/`, then `docs/` — one PR each.
3. Consider enabling Dependabot version-update PRs so this stops re-accumulating.
