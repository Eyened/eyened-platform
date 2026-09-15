# Packaging follow-ups from PR #202: `pyproject.toml` and the GPU worker installs

- **Source:** whyscream's review comment on PR #202, 2026-09-09
  (https://github.com/Eyened/eyened-platform/pull/202#discussion_r3965947492). PR #202 moved
  `deploy/Dockerfile.server`, `worker/Dockerfile.cfi-roi` and both `server-ci.yml` jobs to one
  pip resolution; the two items below were left out of it.

---

## 1. Move `orm` (and possibly `server`) to `pyproject.toml`

**Status:** open

**What:** Replace `orm/setup.py` with a `[project]` table in `orm/pyproject.toml`, and decide
whether `server` becomes a package: today the root `pyproject.toml` holds only pytest and
coverage settings. Then install dependencies from the manifests before copying source, for
example with `uv sync --no-install-project`.

**Why:** Dockerfiles could copy manifests alone ahead of the dependency install, so an `orm`
source edit would stop reinstalling every dependency. A `pyproject.toml` with pip alone does
not give that, because `pip install -e` needs the package source present. The change touches
`deploy/Dockerfile.server`, the four `worker/Dockerfile.*`, both `server-ci.yml` jobs, the dev
venv setup and the `eorm` console-script entry point.

## 2. One pip resolution in the three GPU worker images

**Status:** open

**What:** `worker/Dockerfile.cfi-amd`, `worker/Dockerfile.inference` and
`worker/Dockerfile.layersegmentation` install `server/requirements.txt`, `-e orm` and their
model packages (`git+https://github.com/Eyened/cfi-amd.git`, `retinalysis-inference`,
`nnunetv2`) in separate `RUN pip install` steps on a `pytorch/pytorch` base. Resolve each
image's set in one command, and run `pip check` in the built image.

**Why:** A later install can break an earlier one's pins while pip prints `ERROR` and exits 0.
Measured 2026-09-15 on `python:3.12-slim`: `tifffile 2026.9.9 requires numpy>=2.1, but you have
numpy 2.0.0`, the step succeeded, and `pip check` exited 1. Left out of PR #202 because these
images carry torch and `git+` installs, and verifying a change needs GPU image rebuilds.
