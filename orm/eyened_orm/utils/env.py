from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def load_env_file(env_file: Optional[str], *, override: bool = True) -> None:
    if not env_file:
        return

    path = Path(env_file).expanduser()
    load_dotenv(path, override=override)
