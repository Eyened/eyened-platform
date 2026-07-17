# ESLint ratcheting baseline

`npm run lint` runs `eslint . && prettier --check .` (flat config, `eslint.config.js`).
Every rule is enforced on **new** code. Three high-volume backlogs are grandfathered in
`eslint-suppressions.json` (count-per-file): `@typescript-eslint/no-explicit-any`,
`svelte/require-each-key`, `svelte/prefer-svelte-reactivity`.

## Rules

- **The baseline only shrinks.** Never run `eslint --suppress-all` or
  `--suppress-rule` to hide a _new_ violation. Fix new violations instead.
- Adding a genuinely-unavoidable new violation requires an inline
  `// eslint-disable-next-line <rule> -- <reason>`, reviewed in the PR — not a
  suppressions-file edit. **A disable's stated reason must be true of the code**,
  not an aspiration — prefer making it true by construction (e.g. a type that
  enforces it) over asserting it in prose.

## "But I FIXED an `any` and CI went red!"

That is expected, and it is the ratchet working. Removing a suppressed violation
leaves a stale count, and `eslint .` fails with:

> There are suppressions left that do not occur anymore. To resolve this, re-run
> the command with `--prune-suppressions` to remove unused suppressions.

**Fix:** `cd client && npx eslint . --prune-suppressions` and commit the updated
`eslint-suppressions.json` alongside your change. One extra command; it is what
keeps the baseline honest.

(`eslint-suppressions.json` is listed in `.prettierignore` — eslint rewrites it in
its own format on every prune, so prettier deliberately does not own it. Don't
reformat it by hand.)

Note the exit code is **2** (error), not 1 (violations found) — so a script that
only tests `-eq 1` will misread it. We deliberately do NOT pass
`--pass-on-unpruned-suppressions`: it would keep CI green but let the baseline
become a floor that never lowers.

Two PRs that each prune will conflict in `eslint-suppressions.json`. It's JSON —
regenerate rather than hand-merge: take either side, then re-run `--prune-suppressions`.

## Limitation

Suppressions are counts per file, not per line: within an already-suppressed
file, removing one old violation and adding one new violation of the same rule
(net count unchanged) is not caught. Rare; still far better than disabling.
Adding a violation _without_ removing one IS caught (count goes up → error).
