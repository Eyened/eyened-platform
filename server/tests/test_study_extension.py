"""Load study extensions from a directory of Python modules."""
from __future__ import annotations

from pathlib import Path

import pytest

from server.study_extension import (
    EXTENSIONS_DIR,
    ExtensionLoadError,
    TablesContribution,
    load_extensions,
)

VALID_MODULE = """\
from server.study_extension import TablesContribution

class Registry:
    name = "Registry"
    def applies(self, ctx):
        return True
    def fetch(self, ctx):
        return TablesContribution(groups={"t": [["a", 1]]})

extensions = [Registry()]
"""


def _write(path: Path, name: str, body: str) -> None:
    path.joinpath(name).write_text(body)


def test_the_default_dir_has_no_extensions():
    assert load_extensions(EXTENSIONS_DIR) == ()


def test_a_missing_dir_has_no_extensions(tmp_path: Path):
    assert load_extensions(tmp_path / "missing") == ()


def test_underscore_files_are_skipped(tmp_path: Path):
    _write(tmp_path, "_hidden.py", VALID_MODULE)
    assert load_extensions(tmp_path) == ()


def test_a_valid_module_loads(tmp_path: Path):
    _write(tmp_path, "registry.py", VALID_MODULE)
    loaded = load_extensions(tmp_path)
    assert [e.name for e in loaded] == ["Registry"]
    assert loaded[0].fetch(None).kind == "tables"


def test_missing_extensions_export_fails_load(tmp_path: Path):
    _write(tmp_path, "empty.py", "name = 'Nope'\n")
    with pytest.raises(ExtensionLoadError, match="empty.py"):
        load_extensions(tmp_path)


def test_a_string_extensions_export_fails_load(tmp_path: Path):
    _write(tmp_path, "s.py", "extensions = 'Registry'\n")
    with pytest.raises(ExtensionLoadError, match="s.py"):
        load_extensions(tmp_path)


def test_a_non_protocol_object_fails_load(tmp_path: Path):
    _write(tmp_path, "bad.py", "extensions = [object()]\n")
    with pytest.raises(ExtensionLoadError, match="bad.py"):
        load_extensions(tmp_path)


def test_empty_name_fails_load(tmp_path: Path):
    _write(
        tmp_path,
        "blank.py",
        "class E:\n    name = ''\n    def applies(self, ctx): return True\n"
        "    def fetch(self, ctx): return None\nextensions = [E()]\n",
    )
    with pytest.raises(ExtensionLoadError, match="blank.py"):
        load_extensions(tmp_path)


def test_duplicate_names_fail_load(tmp_path: Path):
    _write(tmp_path, "a.py", VALID_MODULE)
    _write(tmp_path, "b.py", VALID_MODULE)
    with pytest.raises(ExtensionLoadError, match="Registry"):
        load_extensions(tmp_path)


def test_a_broken_import_fails_load(tmp_path: Path):
    _write(tmp_path, "boom.py", "raise RuntimeError('nope')\n")
    with pytest.raises(ExtensionLoadError, match="boom.py"):
        load_extensions(tmp_path)