"""Automatic model version strings for AttributesModel.Version.

Version sources
---------------
- **Python packages** (e.g. ``retinalysis-fundusprep``): distribution version from
  installed package metadata (``importlib.metadata.version``). A new DB row is
  created whenever the installed package version changes.
- **HuggingFace artifacts** (``repo_id:path/to/file.pt``): version derived from
  the repo-relative artifact path (``repo_id/subdir/stem``), stable across runs
  and unique per weights file. Multi-artifact pipelines join sorted parts with
  ``+``.

Ordering
--------
``AttributesModel.Version`` is an opaque provenance label — do not compare
version strings to decide which row is "newest". Selection uses monotonic
``ModelID`` instead (see ``select_attribute_value``). A future change may
introduce an explicit ordinal if registration order is not enough.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path


def package_distribution_version(distribution_name: str) -> str:
    """Version of an installed Python distribution (e.g. retinalysis-fundusprep)."""
    return importlib.metadata.version(distribution_name)


def huggingface_artifact_version(modelstr: str) -> str:
    """Derive a version id from a HuggingFace model string ``repo_id:repo/path/file.pt``."""
    repo_name, repo_fpath = modelstr.split(":", 1)
    path = Path(repo_fpath)
    if path.parent and str(path.parent) != ".":
        return f"{repo_name}/{path.parent}/{path.stem}"
    return f"{repo_name}/{path.stem}"


def huggingface_pipeline_version(*modelstrs: str) -> str:
    """Combine versions for pipelines that load multiple HF artifacts."""
    parts = sorted(huggingface_artifact_version(s) for s in modelstrs)
    return "+".join(parts)
