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
- [Frontend CI Phase 3 — ESLint gate follow-ups](2026-07-16-frontend-ci-phase3-eslint-followups.md)
- [Frontend CI Phase 4 — svelte-check triage](2026-07-20-frontend-ci-phase4-svelte-check-triage.md)
- [Auth service-layer conversion — last unconverted domain](2026-07-27-auth-service-layer-conversion.md)
- [Task→project map: materialize it, or task listings degrade linearly](2026-08-07-task-project-materialized-map.md)
- [DTO layer reads the database unscoped, and no guard covers it](2026-08-07-dto-layer-unscoped-reads.md)
- [Scoped segmentation counts walk four tables on the boot path](2026-08-13-segmentation-project-denormalization.md)
- [`eorm create-user --is-human` can never be false](2026-08-13-create-user-cli-is-human-flag.md)
- [`eorm create-user` writes no `AuditLog` row](2026-08-13-create-user-cli-no-audit-row.md)
- [`alembic upgrade --sql` writes the confirmation prompt into the generated SQL](2026-08-20-alembic-sql-mode-prompt-pollutes-stdout.md)
- [A large `IN` list makes MySQL abandon the range optimizer](2026-08-20-large-in-list-defeats-range-optimizer.md)
