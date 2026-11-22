# Contributing

Questions and ideas: [GitHub Discussions](https://github.com/Eyened/eyened-platform/discussions).

## Tracking work

- All work is tracked as GitHub issues in this repo: bugs, features, maintenance and deferred follow-ups from a review or spec.
- Give each issue one `area/*` label (where) and one `type/*` label (what). `status/*` labels record triage: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`, plus `blocked`.
- `docs/backlog/` is frozen. Add nothing to it. When you start an item there, open an issue for it and delete the item and its index row in the same change.
- PRs target `development`. `Fixes #<n>` only closes issues on PRs into `main`, so close the issue by hand when your PR merges.

## Security

Never report a vulnerability in a public issue, PR, commit message or discussion. Outside contributors: see [SECURITY.md](SECURITY.md). Team members: open an issue with the `security` label in `Eyened/designdocuments` (private, team access only), and describe the fix in the public PR without the exploit.

## AI-generated contributions

Say so in the PR description. Every PR is reviewed by a person before it merges. Instructions for coding agents are in [AGENTS.md](AGENTS.md).
