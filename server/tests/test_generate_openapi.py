import json
import os
import sys

import pytest

from server.scripts import generate_openapi

SCHEMA_REF_PREFIX = "#/components/schemas/"


def _refs(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _refs(item)


@pytest.fixture
def without_required_env(monkeypatch):
    for var in generate_openapi.REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_main_writes_a_schema_whose_refs_all_resolve(monkeypatch, tmp_path):
    """main() writes openapi.json with the hand-added models and every $ref resolvable."""
    out_dir = tmp_path / "out" / "nested"
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_openapi.py", str(out_dir), "--env-file", str(tmp_path / "absent.env")],
    )

    generate_openapi.main()

    document = json.loads((out_dir / "openapi.json").read_text(encoding="utf-8"))
    schemas = document["components"]["schemas"]
    assert {"SegmentationPOST", "SegmentationBase"} <= schemas.keys()
    unresolved = {
        ref
        for ref in _refs(document)
        if not (ref.startswith(SCHEMA_REF_PREFIX) and ref.removeprefix(SCHEMA_REF_PREFIX) in schemas)
    }
    assert unresolved == set()


def test_load_fastapi_app_loads_the_given_env_file(tmp_path, without_required_env):
    """The env file passed in is the one whose settings reach the environment."""
    env_file = tmp_path / "custom.env"
    env_file.write_text(
        "EYENED_DATABASE_USER=from-env-file\nEYENED_DATABASE_PASSWORD=from-env-file\n",
        encoding="utf-8",
    )

    generate_openapi.load_fastapi_app(env_file)

    assert os.environ["EYENED_DATABASE_USER"] == "from-env-file"


@pytest.mark.parametrize("env_file_name", ["missing.env", None], ids=["missing-file", "directory"])
def test_load_fastapi_app_refuses_without_settings(tmp_path, without_required_env, env_file_name):
    """No loadable env file and no settings in the environment exits with a named cause."""
    env_file = tmp_path / env_file_name if env_file_name else tmp_path

    with pytest.raises(SystemExit, match="no env file at"):
        generate_openapi.load_fastapi_app(env_file)
