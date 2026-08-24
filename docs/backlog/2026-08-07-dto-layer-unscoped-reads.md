# DTO layer reads the database unscoped, and no guard covers it

**Status:** open

## Source

Review of the first read-filtering work on branch `feature/rbac-multi-project-tasks`
(2026-08-07). Found by a reviewer sweeping for reads reachable *from* a converted
repository method's return value, and confirmed by reading the call path.

## What

`server/dtos/dto_converter.py:105` (`_registration_attr_to_public_ids`) calls
`build_id_to_public` in `orm/eyened_orm/utils/registration.py:61`, which runs
`ImageInstance.by_columns(session, ImageInstanceID=instance_ids)` on the raw
request `Session` with no `AccessScope` anywhere in the chain. The ids come from
a patient's `Registration` attribute JSON, and the path is reached from
`GET /patients/{patient_id}` whenever that attribute is present.

Two changes were wanted. **The second is done; the first is still open.**

1. **OPEN.** Resolve the id → `PublicID` map through the scoped
   `ImageInstanceRepository` (or filter the returned map to ids the scope can
   read), so an id outside the caller's projects falls back to the raw integer
   exactly as an unresolvable id already does.
2. **DONE (2026-08-10, Task 14 of the same branch).** The read-coverage guard
   now scans `server/dtos/`: `server/tests/test_repository_reads_are_scoped.py`
   pins the current session-touching functions there as an exact set, so the
   *next* DTO converter that reads the database fails a test rather than needing
   a review to catch it. Note what it keys on — the **Session touch**
   (`object_session(...)`, or a `Session`-annotated parameter) — not the query
   itself, because `by_columns` is not in `server/dtos/` at all: a guard
   grepping this directory for the query would find nothing and pass vacuously.
   Its documented blind spots are qualified calls such as
   `sa.orm.object_session(x)` and converters that read through an injected
   repository.

`server/dtos/dto_converter.py:79` (`sess.get(ImageInstance, instance_id)`) is the
same shape but benign — it resolves the already-in-scope annotation's own image.
Worth routing through the same helper when (1) is done, rather than leaving one
converter scoped and one not.

## Why

An authenticated user can learn the 12-character `PublicID` of an image in a
project they have no membership in, and can distinguish "exists but hidden" from
"does not exist" because `normalize_registration_key` falls back to the raw int
when a lookup misses. It is not an image-data leak — `/images/{public_id}` and
its `/data` and `/thumbnail` routes are scoped and 404 — and it only bites where
a patient's Registration JSON actually references another project's image, which
is not the normal shape of that data.

The structural problem was larger than the leak: when this was written,
**`server/dtos/` had no guard at all.** The read-coverage guard scanned only
`orm/eyened_orm/repositories/`, and the route guard passed here because
`GET /patients/{patient_id}` does resolve a scope — so a DTO converter was a
read surface that satisfied every guard while reading whatever it liked.

That structural hole is closed (see change 2). What remains is the specific
leak: the guard is a **ratchet, not a fix** — it freezes the five session-touching
converter methods that exist today so no new one is added silently, and records
them as known and open rather than blessing them as safe. (It was six;
`form_annotation_to_get` came off the pin once it stopped resolving an image id
itself, with a comment on the set explaining why a stale entry would read as a
still-open hole.) Closing this item
means doing change 1 and then shrinking that pinned set.
