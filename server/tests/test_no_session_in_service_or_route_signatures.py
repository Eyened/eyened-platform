"""Guards for design §4: no layer above the repository touches the database.

Repositories take a Session by constructor injection and only flush(); services
take repositories and never hold a Session; get_db (server/db.py) owns the
request transaction.

Two guards live here:

1. Signature guard (test_no_service_holds_a_session,
   test_no_route_handler_holds_a_session): no function under server/services
   or server/routes takes/annotates a parameter as a Session, except a small
   declared exception set (_SIGNATURE_ALLOWED below) plus the get_*_service
   composition-root factories (_is_di_factory).

2. Direct-DB-access guard (test_no_direct_db_access_in_service_or_route_functions):
   a stronger, independent check. The exceptions below weaken guard 1 (several
   functions legitimately hold a Session parameter), so this guard scans for
   the thing that actually matters -- a bare `session`/`db` local or parameter
   being used to touch the database directly (``session.query(...)``,
   ``db.execute(...)``, etc). Repository/AuditService internals reach the
   database via ``self._session.method(...)``, which this pattern deliberately
   does not match: the call's receiver is an attribute access on ``self``, not
   a bare ``session``/``db`` name, and repositories owning the session is the
   design, not a violation of it.

Exemptions, and what would remove them:

- server/routes/import_api.py::import_single_image (R1) is exempted by name in
  both guards -- not a whole-file exclusion; an earlier version of this guard
  skipped the entire file, which would have hidden any handler later added to
  it. Human decision: that module is slated for deprecation and will not be
  converted. It legitimately holds a Session for ``ImportRun.apply()`` and for
  the explicit ``session.rollback()`` on its caught-failure path (Task 17).
- audit_service.py's ``_drain``/``_clear`` are SQLAlchemy ``after_commit`` /
  ``after_rollback`` event-listener callbacks; SQLAlchemy dictates their
  ``(session)`` signature. They are part of the already-declared AuditService
  audit-sink exception -- the original plan's ``_ALLOWED`` named only
  ``AuditService.__init__``, which was a clerical gap, not a design decision.
- Five auth.py functions (``get_current_user``, ``check_login``,
  ``check_oidc_login``, ``CurrentUser.get_creator``, ``creator_to_response``)
  are auth resolvers that legitimately read/write ``Creator`` directly ahead
  of the request's authorization scope existing.
- Seven auth.py route handlers (``login``, ``get_token``,
  ``get_current_user_info``, ``change_password``, ``register_user``,
  ``refresh_token``, ``oidc_authenticate``) hold ``session`` ONLY to forward
  it to one of the five resolvers above, or to ``create_user`` (also a
  declared exception). ``change_password``/``register_user`` separately depend
  on ``AuditService`` via ``Depends(get_audit_service)``, a DI factory
  parameter -- structurally exempt (``_is_di_factory`` below), not a session
  forward. The plan exempted the resolver callees but never named the callers
  that must obtain and forward the session -- fixing that omission is what
  this exemption set is. What would remove it: converting the auth resolvers
  into FastAPI dependencies, so route handlers stop receiving a Session at
  all and have nothing left to forward. That conversion is out of scope for
  this guard.

Blind spot: both scans key on the bare names ``session``/``db`` (parameter
name for guard 1, call-receiver name for guard 2), so a local alias (e.g.
``s = db; s.query(...)``) would evade both. Currently inert -- every DB entry
point in scope arrives as a ``Depends(get_db)`` parameter, and guard 1's
annotation check (``text.endswith("Session")``) still catches the
parameter-rename variant -- but a future maintainer introducing such an alias
would not be caught here.
"""

import ast
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[1]  # server/
_SERVICES = _ROOT / "services"
_ROUTES = _ROOT / "routes"


def _is_di_factory(name: str) -> bool:
    """The get_*_service factories (incl. get_audit_service) are the composition
    root: they take ``db: Session = Depends(get_db)`` to wire the stack. That is
    the intended seam, not a service/handler holding a Session."""
    return name.startswith("get_") and name.endswith("_service")


# --- Guard 1: signature -----------------------------------------------------
#
# Declared exceptions: (filename, function_name) -> why. See module docstring
# for the full rationale of each group below.
_SIGNATURE_ALLOWED: dict[tuple[str, str], str] = {
    # Auth resolvers that read/write Creator directly.
    ("auth.py", "get_current_user"): "auth resolver -- reads Creator pre-scope",
    ("auth.py", "check_login"): "auth resolver -- verifies credentials against Creator",
    ("auth.py", "check_oidc_login"): "auth resolver -- finds/creates Creator from OIDC claims",
    ("auth.py", "get_creator"): "CurrentUser.get_creator -- auth resolver, reads Creator by id",
    ("auth.py", "creator_to_response"): "read-only response helper with an optional session param",
    # AuditService: audit sink; owns the session for its AuditLog write, like a repository.
    ("audit_service.py", "__init__"): "AuditService.__init__ -- audit sink owns its session",
    # R2: SQLAlchemy event-listener callbacks; signature is SQLAlchemy-mandated.
    ("audit_service.py", "_drain"): "after_commit listener callback (SQLAlchemy-mandated signature)",
    ("audit_service.py", "_clear"): "after_rollback/after_soft_rollback listener callback (SQLAlchemy-mandated signature)",
    # R3: forwarding-only route handlers (see module docstring).
    ("auth.py", "login"): "forwards session to check_login/creator_to_response only",
    ("auth.py", "get_token"): "forwards session to check_login/creator_to_response only",
    ("auth.py", "get_current_user_info"): "forwards session to CurrentUser.get_creator/creator_to_response only",
    ("auth.py", "change_password"): "forwards session to check_login/creator_to_response only",
    ("auth.py", "register_user"): "forwards session to create_user/creator_to_response only",
    ("auth.py", "refresh_token"): "forwards session to CreatorRepository/creator_to_response only",
    ("auth.py", "oidc_authenticate"): "forwards session to check_oidc_login/creator_to_response only",
    # R1: import_api.py is slated for deprecation (see module docstring); only
    # import_single_image holds a Session, for ImportRun.apply().
    ("import_api.py", "import_single_image"): "human decision: import_api.py is slated for deprecation; holds Session for ImportRun.apply()",
}


def _offenders(root: pathlib.Path) -> list[str]:
    bad: list[str] = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if (path.name, node.name) in _SIGNATURE_ALLOWED or _is_di_factory(node.name):
                continue
            for arg in [*node.args.args, *node.args.kwonlyargs]:
                ann = getattr(arg, "annotation", None)
                text = ast.unparse(ann) if ann is not None else ""
                if arg.arg in {"session", "db"} or text.endswith("Session"):
                    bad.append(f"{path.relative_to(_ROOT.parent)}::{node.name}({arg.arg})")
    return bad


def test_no_service_holds_a_session():
    """No function under server/services takes or annotates a Session (design §4)."""
    assert _offenders(_SERVICES) == []


def test_no_route_handler_holds_a_session():
    """No function under server/routes takes a Session, except the declared exceptions."""
    assert _offenders(_ROUTES) == []


# --- Guard 2 (R5): direct DB-access AST scan --------------------------------
#
# Guard 1 checks signatures only, and R1-R3 exempt functions that legitimately
# hold a Session parameter -- which weakens that check as a discriminator.
# This guard enforces the design's actual property directly: scan for calls
# of the form `session.<method>(...)` / `db.<method>(...)`, for a bare
# session/db local or parameter, where <method> touches the database.

_DB_METHODS = {
    "query", "execute", "scalars", "scalar", "get",
    "add", "add_all", "delete", "merge", "flush", "commit", "rollback", "refresh",
}

# The five auth resolvers and import_single_image are the only functions in
# scope that legitimately call session.<method>()/db.<method>() directly. The
# seven R3 forwarding handlers need no entry -- they pass `session` as a plain
# argument and never call a method on it themselves, so they are not
# offenders here in the first place.
_DB_ACCESS_ALLOWED: dict[tuple[str, str], str] = {
    ("auth.py", "get_current_user"): "auth resolver -- reads Creator pre-scope",
    ("auth.py", "check_login"): "auth resolver -- verifies credentials against Creator",
    ("auth.py", "check_oidc_login"): "auth resolver -- finds/creates Creator from OIDC claims",
    ("auth.py", "get_creator"): "CurrentUser.get_creator -- auth resolver, reads Creator by id",
    ("auth.py", "creator_to_response"): "read-only response helper with an optional session param",
    # R1: human decision: import_api.py is slated for deprecation. Calls
    # session.rollback() on the caught-failure path (Task 17).
    ("import_api.py", "import_single_image"): "human decision: import_api.py is slated for deprecation; calls session.rollback() on the caught-failure path",
}


def _db_access_offenders(root: pathlib.Path) -> list[str]:
    bad: list[str] = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if (path.name, node.name) in _DB_ACCESS_ALLOWED:
                continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                    continue
                receiver = call.func.value
                if (
                    isinstance(receiver, ast.Name)
                    and receiver.id in {"session", "db"}
                    and call.func.attr in _DB_METHODS
                ):
                    bad.append(
                        f"{path.relative_to(_ROOT.parent)}::{node.name}({receiver.id}.{call.func.attr})"
                    )
    return bad


def test_no_direct_db_access_in_service_or_route_functions():
    """No function under server/routes or server/services calls session.<m>()/db.<m>() directly (design §4; R5)."""
    assert _db_access_offenders(_SERVICES) + _db_access_offenders(_ROUTES) == []
