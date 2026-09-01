# `is_admin` makes `scope.require` vacuous, so an administrator gets 500 where anyone else gets 404

**Status:** open

## Source

Task 7 review, branch `feature/tasks-page-performance`, 2026-08-21. Found while
adding the declaration contract to `POST /task`; reproduced by the implementer
and independently by the reviewer. Pre-existing behaviour, not introduced by that
task — it became visible because `POST /task` now takes project ids as input.

## What

`POST /task` with a **nonexistent** project id returns **500** for an
administrator and a clean **404** for everyone else.

`scope.require` passes vacuously when `is_admin` is set: an administrator is
allowed every project, including ids that do not exist, so the request proceeds
to the flush and dies on a foreign key instead of being refused at the boundary.
A non-admin's scope is a concrete set of memberships, so a nonexistent id simply
is not in it and the request is refused cleanly.

The same vacuity applies anywhere an administrator's `scope.require` is the only
thing standing between user input and a foreign key.

## Why

Low urgency, and deliberately not fixed under Task 7 — no spec or plan section
asks for an existence check there, and inventing one inside a task about
containment would have been scope creep.

It is worth recording rather than dropping for two reasons. First, it is
**latent rather than absent**: `Creator.IsAdmin` is true on **zero rows** today
(`eorm init-admin` was never run, though `grant-all` was), so nothing hits it in
production right now — but the cutover's step 2 exists precisely to create an
administrator, and this becomes reachable the day it runs.

Second, the shape is the interesting part: an authorization overlay that *widens*
access silently converts a validation failure into an internal error. Fixing it
belongs with a decision about whether `require` should assert existence as well
as permission, which is broader than one route.

## Related

- The same `is_admin` vacuity is why route-level 409 tests written under the
  `client` fixture (which overrides scope with `admin_scope()`) prove the
  containment contract only for a user type that currently has zero rows. Task 7
  carries `test_a_grader_in_both_is_refused_an_undeclared_image` for that reason.
