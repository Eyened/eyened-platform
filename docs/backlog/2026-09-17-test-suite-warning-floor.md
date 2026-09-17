# The suite's warning floor hides a new warning

**Status:** open

## Source

RBAC admin P1 whole-branch review, 2026-09-17.

## What

The full suite reports 1217 warnings; `server/tests` alone reports 579. Three
causes account for most of the volume:

- A pydantic `UserWarning`: `FormSchemaBase`'s `schema` field name shadows a
  `BaseModel` attribute (`server/dtos/dtos_main.py`).
- `passlib` importing the deprecated stdlib `crypt` module.
- `passlib`'s argon2 backend accessing the deprecated `argon2.__version__`.

Fix shape: a `filterwarnings` entry per known cause in
`pyproject.toml`'s `[tool.pytest.ini_options]`, plus `error` for everything
else, so an unrecognized warning fails the suite instead of being buried.

## Why

At this volume, warnings cannot do the one thing they exist for: flagging a
*new* problem. A regression that adds one more `DeprecationWarning` is
invisible next to 1200+ pre-existing ones. Naming the known causes and
erroring on the rest turns the warning stream back into a signal.
