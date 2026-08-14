#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import importlib
from typing import Optional

from fastapi import FastAPI
from dotenv import load_dotenv




def project_root() -> Path:
    """Return the repository root.

    This file lives at <repo>/deploy/scripts/, so the root is two levels up.
    Both callers below depend on that depth: `load_fastapi_app` puts the root
    on sys.path to import `server.main`, and `default_output_dir` resolves the
    docs tree against it. Move this file and both break silently — the import
    fails, or the schema is written under the wrong directory.

    A third thing depends on this file's location without coming through here:
    `load_fastapi_app` calls `load_dotenv()`, which walks up from *this file's*
    directory rather than from the root. From `deploy/scripts/` that resolves
    `deploy/.env` — the file `bootstrap.sh` writes. With no `.env` anywhere up
    the tree the import fails in pydantic on required settings.
    """
    return Path(__file__).resolve().parents[2]


def default_output_dir() -> Path:
    """Return default docs output directory."""
    return project_root() / "docs/src/content/docs/api"


def load_fastapi_app() -> FastAPI:
    """Import FastAPI app from `server.main` (prefers `app_api`)."""
    load_dotenv()
    root = project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    module = importlib.import_module("server.main")
    app: Optional[FastAPI] = getattr(module, "app_api", None) or getattr(module, "app", None)
    if app is None:
        raise RuntimeError(
            "No FastAPI app found in eyened_platform.server.main (expected `app_api` or `app`)."
        )
    return app



def main() -> None:
    """Generate OpenAPI JSON and write it to the given directory."""
    parser = argparse.ArgumentParser(
        description="Generate OpenAPI schema from the FastAPI app."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=str(default_output_dir()),
        help="Directory to store the OpenAPI file (default: docs path).",
    )
    args = parser.parse_args()

    out_dir = Path(args.directory).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "openapi.json"

    app = load_fastapi_app()
    schema = app.openapi()

    from server.dtos.dtos_main import SegmentationPOST, SegmentationBase
    # these models are not automatically added by the fastapi openapi generator
    # so we need to add them manually
    models_to_add = [
        SegmentationPOST,
        SegmentationBase,
    ]
    for model in models_to_add:
        schema["components"]["schemas"][model.__name__] = model.model_json_schema(ref_template="#/components/schemas/{model}")

    out_file.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OpenAPI schema written to {out_file}")


if __name__ == "__main__":
    main()
