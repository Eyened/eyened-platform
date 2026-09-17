# `deploy-validate.yml` never builds a Docker image

- **Source:** Wave H whole-PR review of the `deploy/` consolidation (PR #202), 2026-09-17,
  commit range `e03e4f34..6dca929e`. Verified and deferred by the repository owner rather than
  fixed in that wave.
- **Files:** `.github/workflows/deploy-validate.yml`, `.dockerignore`,
  `deploy/Dockerfile.client`, `deploy/Dockerfile.server`.

---

**Status:** open

**What:** `deploy-validate.yml`'s `paths:` filter triggers on `deploy/**`, `worker/**` and
`.dockerignore` — which covers every Dockerfile in the repo, since they all live under those
two directories — but no step in its 666 lines ever builds an image. Every `docker` invocation
in the job is `docker compose version`, `docker compose config`, or `docker run
nginx:1.27-alpine nginx -t`; everything else is shell/text assertions. Checked all four
workflows under `.github/workflows/` (`client-ci.yml`, `deploy.yml`, `server-ci.yml`,
`deploy-validate.yml`) for `docker build`, `docker buildx`, or a `compose build` invocation:
none exists. `deploy.yml` is the unrelated docs-site GitHub Pages job.

**The concrete exposure:** `.dockerignore:17-18` excludes `deploy` wholesale and then
re-includes one file under it:

```
17: deploy
18: !deploy/entrypoint-client.sh
```

`deploy/Dockerfile.client:38` depends on that re-inclusion surviving:

```
COPY deploy/entrypoint-client.sh /entrypoint.sh
```

Re-including a child path after excluding its parent directory is a case where Docker's
`.dockerignore` semantics deliberately diverge from git's, and it has also differed between the
classic builder and BuildKit/fsutil. If a future Docker/BuildKit change (or an edit to
`.dockerignore`) breaks that combination, the failure surfaces as a build error on a
developer's machine during `./eyened up` — CI stays green because it never runs the build that
would catch it.

The same blind spot covers `deploy/Dockerfile.server:19-21`:

```
COPY orm /app/orm
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install -r /app/server/requirements.txt -e /app/orm
```

That copy order — `orm` and the requirements file ahead of the rest of `server` — is what the
Dockerfile's own "one resolution for orm and the server together" comment rests on. Only the
pip closure is exercised in CI, by `server-ci.yml`'s `pip install -e ./orm -r
server/test-requirements.txt` step; the Dockerfile layer order that expresses the same idea is
never built or checked.

**Suggested fix:** add a `docker compose build` step to `deploy-validate.yml` covering at least
`client`, and extend the job's `paths:` filter with `client/**`, `server/**` and `orm/**` so the
step is actually triggered by what it covers.

**Why deferred:** a real build step needs layer caching wired up and the job's current
`timeout-minutes: 10` raised — more than this wave is taking on.
