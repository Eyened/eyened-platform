# Backlog

Tracks important follow-up work surfaced during reviews, planning, and implementation
that is intentionally deferred rather than done inline. Each item should capture:

- **Source** — where it came from (PR review, spec, discussion) with a link.
- **What** — the concrete change.
- **Why** — the motivation / risk if left undone.
- **Status** — `open`, `in progress`, or `done`.

Keep entries short. When an item is picked up, link the PR/commit and mark it done.

## Index

- [PR #145 — RBAC Step 1 service layer](2026-07-16-pr145-rbac-step1-review.md)
- [Backend Python lint gate (ruff) — follow-up to #118](2026-07-16-backend-ruff-lint-followup.md)
- [Dependabot vulnerability alerts](2026-07-16-dependabot-vulnerabilities.md)
- [Follow-ups from Frontend CI Phase 3 — ESLint gate](2026-07-16-frontend-ci-phase3-eslint-followups.md)
- [Frontend CI Phase 4 — svelte-check triage](2026-07-20-frontend-ci-phase4-svelte-check-triage.md)
- [Auth service-layer conversion — last unconverted domain](2026-07-27-auth-service-layer-conversion.md)
- [Task→project map: materialize it, or task listings degrade linearly](2026-08-07-task-project-materialized-map.md)
- [DTO layer reads the database unscoped, and no guard covers it](2026-08-07-dto-layer-unscoped-reads.md)
- [Scoped segmentation counts walk four tables per request, and the boot path pays it](2026-08-13-segmentation-project-denormalization.md)
- [`eorm create-user --is-human` can never be false](2026-08-13-create-user-cli-is-human-flag.md)
- [`eorm create-user` writes no `AuditLog` row](2026-08-13-create-user-cli-no-audit-row.md)
- [Phase C — make the coverage gates block a merge](2026-08-14-coverage-gate-enforcement.md)
- [`form_validation` cannot be imported — `DBManager` does not exist](2026-08-14-form-validation-dbmanager-broken.md)
- [`alembic upgrade --sql` writes the confirmation prompt into the generated SQL](2026-08-20-alembic-sql-mode-prompt-pollutes-stdout.md)
- [A large `IN` list makes MySQL abandon the range optimizer](2026-08-20-large-in-list-defeats-range-optimizer.md)
- [`docs/rbac-operations.md` is two documents in one file](2026-08-21-rbac-operations-doc-has-two-homes.md)
- [`is_admin` makes `scope.require` vacuous, so an administrator gets 500 where anyone else gets 404](2026-08-21-admin-scope-vacuity-turns-404s-into-500s.md)
- [The segmentation zarr store has no write lock](2026-08-24-zarr-storage-write-lock.md)
- [API pool sizing assumes one connection per thread; a request takes several](2026-08-24-api-pool-sizing-multi-hop-checkout.md)
- [Cross-project data cleaning has no safe path, and the ORM actively misleads](2026-08-25-cross-project-data-cleaning-has-no-safe-path.md)
