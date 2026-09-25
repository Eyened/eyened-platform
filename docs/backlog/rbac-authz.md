# RBAC authorization

### Scope the registration id → `PublicID` lookup in the DTO layer
- **Status:** open
- **Source:** review of `feature/rbac-multi-project-tasks`, 2026-08-07
- **Problem:** `_registration_attr_to_public_ids` (`server/dtos/dto_converter.py:105`) calls `build_id_to_public` (`orm/eyened_orm/utils/registration.py`) on the raw session, no `AccessScope`. `GET /patients/{id}` then reveals the `PublicID` of an image in a project the caller cannot see, and distinguishes "hidden" from "missing" (a miss falls back to the raw int).
- **Fix:** resolve through the scoped `ImageInstanceRepository` so an out-of-scope id falls back to the raw int; route `dto_converter.py:79` (`sess.get(ImageInstance, ...)`, benign) through the same helper; then shrink the pinned set in `server/tests/test_repository_reads_are_scoped.py`.

### Stop `scope.require` passing vacuously for an administrator on nonexistent ids
- **Status:** open
- **Source:** Task 7 review, `feature/tasks-page-performance`, 2026-08-21
- **Problem:** `AccessScope.require` (`orm/eyened_orm/authz/scope.py`) allows an admin every id, including ones that do not exist, so `POST /task` with a nonexistent project is a 500 (FK failure at flush) for an admin and a 404 for everyone else. Applies wherever an admin's `require` is all that sits between input and an FK.
- **Fix:** decide whether `require` asserts existence as well as permission (broader than one route), or add existence checks at the affected services.

### Make the session guards fail on stale allow-list entries
- **Status:** open
- **Source:** RBAC admin P1 review, 2026-09-17
- **Problem:** `_offenders` / `_db_access_offenders` in `server/tests/test_no_session_in_service_or_route_signatures.py` only test `in allowed`, so an entry naming a moved/renamed/deleted function is inert and fails nothing (unlike `_TRUSTED_CALLERS` in `test_escalation_paths.py`, which asserts the exact set).
- **Fix:** collect the `(key_path, name)` pairs actually skipped and assert `set(allowed) <= matched`; give the untouched entries (`audit_service.py` `__init__`/`_drain`/`_clear`, `get_access_scope`, `import_single_image`) a "what would remove it" clause.

### Decide whether `AuthService.change_password` keeps its `actor` parameter
- **Status:** open (design decision)
- **Source:** RBAC admin P1 review, 2026-09-17
- **Problem:** the route passes `ActingUser(current_user)` although the subject from `authenticate()` is the same row, so the parameter is untestable and carries the `_ACTOR_PARAMETER_ALLOWED` exemption in `server/tests/test_scope_is_constructor_state.py`.
- **Fix:** if admin-driven resets of another user's password via this method are never built, derive the actor from the subject and delete the exemption; otherwise keep it.
