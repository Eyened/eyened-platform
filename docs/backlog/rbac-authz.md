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
