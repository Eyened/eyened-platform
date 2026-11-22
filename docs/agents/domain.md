# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root, if it exists.
- **ADRs in `Eyened/designdocuments`**, folder `decisions/` (MADR 4.0.0, one numbered sequence). That repo is private: if `gh` cannot read it, proceed without the ADRs. Read the ones that touch the area you're about to work in: `gh api repos/Eyened/designdocuments/contents/decisions --jq '.[].name'`, then `gh api repos/Eyened/designdocuments/contents/decisions/<file> --jq .content | base64 -d`. Proposed ADRs are open draft PRs there: `gh pr list -R Eyened/designdocuments --draft`.

If any of these don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo:

```
eyened-platform/
├── GLOSSARY.md
└── ...

designdocuments/
└── decisions/
    ├── 0001-<title>.md
    └── ...
```

There is no `docs/adr/` in this repo. A new ADR is a draft PR in `Eyened/designdocuments` that adds `decisions/<next number>-<title>.md` at status `proposed`; show its full text to the maintainer before pushing.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
