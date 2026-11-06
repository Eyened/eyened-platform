# Agent instructions

Shared instructions for coding agents working in this repo. Personal agent config (such as `CLAUDE.md`) stays untracked; import this file from it.

## Agent skills

### Issue tracker

GitHub Issues in `Eyened/eyened-platform`; security findings go to issues in the private `Eyened/designdocuments` repo (label `security`); `docs/backlog/` is frozen. See `docs/agents/issue-tracker.md`.

### Triage labels

The five triage states map to `status/*` labels, and `bug`/`enhancement` to `type/bug`/`type/feature`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` at the root; ADRs live in the private `Eyened/designdocuments` repo under `decisions/`. See `docs/agents/domain.md`.
