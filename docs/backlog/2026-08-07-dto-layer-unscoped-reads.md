# DTO layer reads the database unscoped, and no guard covers it

**Status:** open

## Source

Review of the first read-filtering work on branch `feature/rbac-multi-project-tasks`
(2026-08-07). Found by a reviewer sweeping for reads reachable *from* a converted
repository method's return value, and confirmed by reading the call path.

## What

`server/dtos/dto_converter.py:100` (`_registration_attr_to_public_ids`) calls
`build_id_to_public` in `orm/eyened_orm/utils/registration.py:61`, which runs
`ImageInstance.by_columns(session, ImageInstanceID=instance_ids)` on the raw
request `Session` with no `AccessScope` anywhere in the chain. The ids come from
a patient's `Registration` attribute JSON, and the path is reached from
`GET /patients/{patient_id}` whenever that attribute is present.

Two changes are wanted:

1. Resolve the id → `PublicID` map through the scoped `ImageInstanceRepository`
   (or filter the returned map to ids the scope can read), so an id outside the
   caller's projects falls back to the raw integer exactly as an unresolvable id
   already does.
2. Extend the repository read-coverage guard to `server/dtos/`, so the next DTO
   converter that reads the database is caught by a test rather than by a review.

`server/dtos/dto_converter.py:74` (`sess.get(ImageInstance, instance_id)`) is the
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

The structural problem is larger than the leak: **`server/dtos/` has no guard at
all.** The planned read-coverage guard scans `orm/eyened_orm/repositories/`, and
the planned route guard passes here because `GET /patients/{patient_id}` does
resolve a scope. A DTO converter is therefore a read surface that satisfies every
guard while reading whatever it likes.
