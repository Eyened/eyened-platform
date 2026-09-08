# Release notes

Release notes live in the documentation site, not in this file:

- **Published:** https://eyened.github.io/eyened-platform/release_notes/
- **Source:** [`docs/src/content/docs/release_notes.mdx`](docs/src/content/docs/release_notes.mdx)

That page is the only copy. This file used to hold a second one, and the two drifted —
the v2026.07.0 notes reached the site and never reached here.

## Adding an entry

Add it to the `## Unreleased` section of `docs/src/content/docs/release_notes.mdx`, in the
**same pull request** that changes behaviour. Reconstructing the list at release time is how
things get missed.

When a release is cut, rename `## Unreleased` to the version heading and open a fresh
`## Unreleased` above it.
