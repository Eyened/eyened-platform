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
``version_sort_key`` compares versions for "pick newest" and ``min_version``
filtering:

1. PEP 440 semver/release strings (package versions like ``1.1.0``) via
   ``packaging.version.Version``
2. Opaque artifact ids (``Eyened/vascx/odfd/odfd_march25``) via stable string
   ordering as fallback

No per-model ``VERSION_ORDER`` table is required.
"""

from __future__ import annotations

import importlib.metadata
from functools import total_ordering
from pathlib import Path
from typing import Iterable

from packaging.version import InvalidVersion, Version


@total_ordering
class _VersionSortKey:
    """Comparable wrapper: semver first, then opaque strings."""

    __slots__ = ("_kind", "_value")

    def __init__(self, version: str) -> None:
        try:
            self._kind = 0
            self._value = Version(version)
        except InvalidVersion:
            self._kind = 1
            self._value = version

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _VersionSortKey):
            return NotImplemented
        return (self._kind, self._value) == (other._kind, other._value)

    def __lt__(self, other: _VersionSortKey) -> bool:
        if self._kind != other._kind:
            return self._kind < other._kind
        return self._value < other._value


def version_sort_key(version: str) -> _VersionSortKey:
    return _VersionSortKey(version)


def version_at_least(version: str, min_version: str) -> bool:
    return version_sort_key(version) >= version_sort_key(min_version)


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


def best_version(versions: Iterable[str]) -> str | None:
    keys = list(versions)
    if not keys:
        return None
    return max(keys, key=version_sort_key)
