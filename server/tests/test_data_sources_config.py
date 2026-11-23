"""The data sources file is checked when it is loaded, so a bad file stops startup."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.config import load_data_sources


def _write(tmp_path, *entries: tuple[str, str]):
    path = tmp_path / "data_sources.yaml"
    lines = ["sources:"]
    for name, url in entries:
        lines += [f"  - name: {name}", f"    url: {url}", "    projects: [Alpha]"]
    path.write_text("\n".join(lines) + "\n")
    return path


def test_duplicate_names_are_rejected(tmp_path):
    path = _write(tmp_path, ("Registry", "http://h/a"), ("Registry", "http://h/b"))

    with pytest.raises(ValidationError, match="Duplicate data source name: Registry"):
        load_data_sources(path)


@pytest.mark.parametrize("url", ["http://h/{study}", "http://h/{}", "http://h/{patient.id}"])
def test_unknown_placeholders_are_rejected(tmp_path, url):
    with pytest.raises(ValidationError, match="placeholder"):
        load_data_sources(_write(tmp_path, ("Registry", url)))


@pytest.mark.parametrize("url", ["ftp://h/x", "file:///etc/passwd", "h/x"])
def test_non_http_schemes_are_rejected(tmp_path, url):
    with pytest.raises(ValidationError, match="http or https"):
        load_data_sources(_write(tmp_path, ("Registry", url)))


def test_a_valid_file_loads(tmp_path):
    path = _write(
        tmp_path,
        ("Registry", "https://h/{project}/{patient}/{date}"),
        ("Other", "http://h/fixed"),
    )

    assert [s.name for s in load_data_sources(path)] == ["Registry", "Other"]
