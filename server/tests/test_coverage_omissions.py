"""Coverage omissions are mechanically justified, not merely convenient.

``[tool.coverage.run] omit`` in ``pyproject.toml`` hides code from the patch
gate, which makes editing it the cheapest way to turn a failing gate green.
This guard enforces the design's criterion in three directions:

1. every omitted production module must fail to import because a third-party
   package CI deliberately does not install is absent -- "untestable here",
   not "inconvenient to test";
2. every module in ``KNOWN_UNIMPORTABLE`` must still raise ``ImportError``, so
   repairing one forces its removal from the set;
3. ``# pragma: no cover`` -- a per-line omit that directions 1 and 2 cannot
   see -- may appear only as often as ``KNOWN_PRAGMA_SITES`` records.

Scope, stated so the guard is not over-trusted.

Direction 1 is weaker than the sentence above it. It accepts any
``ModuleNotFoundError`` whose top-level module is not repo code; it does not
check that the absent package is one CI was *meant* to skip. So a module that
fails on a typo (``import pandsa``) or on a dependency someone forgot to add to
``requirements.txt`` can be omitted and this guard will allow it. The gap is
narrow in practice -- hiding code this way means breaking its imports, which
defeats the purpose -- but the accidental path is real: a red CI, a forgotten
requirement, and ``omit`` is the fastest way to green. Closing it would mean
naming the deliberate exclusions (today: ``torch``) and rejecting everything
else. That was considered and deferred; if you are here because the omit list
grew, reconsider it.

Direction 2 checks only the modules named in the set. It does not sweep the
tree for newly-broken modules. One that anything imports already fails this
suite; one that nothing imports reports 0% coverage and reddens the patch gate
as soon as a PR touches it.
"""

from __future__ import annotations

import importlib
import pathlib
import tomllib

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PYPROJECT = _ROOT / "pyproject.toml"
_SOURCE_TREES = (_ROOT / "server", _ROOT / "orm")

# `omit` entries that exclude the tests themselves rather than production code.
# Direction 1 skips these; every other entry must resolve to real .py files.
_TEST_GLOBS = frozenset({"*/tests/*", "*/conftest.py"})

# Modules that do not import today and are deliberately NOT omitted from
# coverage. Shrink only -- repairing one makes direction 2 fail until it is
# removed from here. See the backlog entry on form_validation / DBManager.
KNOWN_UNIMPORTABLE = frozenset(
    {
        "eyened_orm.form_validation",
        "eyened_orm.form_validation.validator",
        "eyened_orm.form_validation.form_validation_example",
    }
)

# Grandfathered `# pragma: no cover`, as a per-file count -- the same shape as
# client/eslint-suppressions.json. A line anchor would break on any edit above
# the pragma; a whole-file exemption would hide a second one in the same file.
KNOWN_PRAGMA_SITES = {
    "orm/eyened_orm/inference/attribute_inference.py": 1,
}


def _omit_globs() -> list[str]:
    config = tomllib.loads(_PYPROJECT.read_text())
    omit = config["tool"]["coverage"]["run"]["omit"]
    assert omit, "`omit` is empty -- the guard would check nothing"
    return omit


def _module_name(path: pathlib.Path) -> str:
    """Repo path -> importable module name.

    ``orm/`` is the packaging root for ``eyened_orm`` (CI runs
    ``pip install -e ./orm``), so it is stripped. ``server`` is importable from
    the repo root because ``pyproject.toml`` sets ``pythonpath = ["."]``.
    """
    parts = list(path.relative_to(_ROOT).with_suffix("").parts)
    if parts[0] == "orm":
        parts = parts[1:]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def test_every_omitted_module_is_unimportable_for_an_external_reason():
    """Omitted production modules fail to import on an absent third-party package."""
    checked = 0
    for glob in _omit_globs():
        if glob in _TEST_GLOBS:
            continue
        assert not glob.startswith("*"), (
            f"{glob!r} is neither a known test-exclusion nor a repo-relative path, "
            "so the guard cannot resolve it to modules -- it would omit code unchecked"
        )
        paths = sorted(p for p in _ROOT.glob(glob) if p.suffix == ".py")
        assert paths, f"{glob!r} matched no .py files -- it omits nothing, so delete it"
        for path in paths:
            name = _module_name(path)
            try:
                importlib.import_module(name)
            except ModuleNotFoundError as exc:
                missing = (exc.name or "").split(".")[0]
                assert missing and missing not in {"server", "eyened_orm"}, (
                    f"{name} fails on {exc.name!r}, which is repo code rather than an "
                    "absent third-party package -- fix it or delete it, do not omit it"
                )
            except ImportError as exc:
                raise AssertionError(
                    f"{name} fails with {exc!r}. That is broken repo code, not code "
                    "CI cannot install -- fix it or delete it, do not omit it"
                ) from exc
            else:
                raise AssertionError(
                    f"{name} imports cleanly, so it is testable and must not be "
                    "omitted from coverage. Write the test instead."
                )
            checked += 1
    assert checked, "no omitted production modules were checked -- guard would pass vacuously"


def test_known_unimportable_modules_still_fail():
    """The unimportable set is shrink-only: a repaired module must leave it."""
    assert KNOWN_UNIMPORTABLE, "KNOWN_UNIMPORTABLE is empty -- guard would check nothing"
    repaired = []
    for name in sorted(KNOWN_UNIMPORTABLE):
        try:
            importlib.import_module(name)
        except ImportError:
            continue
        repaired.append(name)
    assert not repaired, (
        f"{repaired} now import cleanly. Remove them from KNOWN_UNIMPORTABLE -- "
        "the set only shrinks."
    )


def test_no_new_pragma_no_cover():
    """`# pragma: no cover` appears only where grandfathered, and no more often."""
    found: dict[str, int] = {}
    scanned = 0
    for tree in _SOURCE_TREES:
        assert tree.is_dir(), f"{tree} is not a directory -- guard would scan nothing"
        for path in tree.rglob("*.py"):
            # Test files are already excluded from coverage by `omit`, so a
            # pragma there is inert -- and skipping them stops this guard from
            # flagging its own docstring.
            if "__pycache__" in path.parts or "tests" in path.parts:
                continue
            if path.name == "conftest.py":
                continue
            scanned += 1
            count = path.read_text().count("# pragma: no cover")
            if count:
                found[path.relative_to(_ROOT).as_posix()] = count
    assert scanned, "no .py files scanned -- guard would pass vacuously"
    assert found == KNOWN_PRAGMA_SITES, (
        "`# pragma: no cover` is a per-line coverage omit that the omit list "
        f"cannot see. Expected {KNOWN_PRAGMA_SITES}, found {found}. A new one "
        "needs review in the PR, not a baseline edit; a removed one must shrink "
        "the baseline."
    )
