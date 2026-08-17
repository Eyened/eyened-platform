from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def load_env_file(env_file: Optional[str], *, override: bool = True) -> None:
    if not env_file:
        return

    path = Path(env_file).expanduser()
    load_dotenv(path, override=override)


_TRUTHY_FLAG_VALUES = frozenset({"1", "true", "yes"})


def env_flag_enabled(value: Optional[str]) -> bool:
    """True only for an explicit opt-in value.

    Deliberately an allowlist rather than a truthiness test: this parses
    opt-outs from safety prompts, where a value of "false" enabling the
    flag is the wrong failure direction.
    """
    return value is not None and value.strip().casefold() in _TRUTHY_FLAG_VALUES
