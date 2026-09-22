# Admin account writes reach non-human `Creator` rows

**Status:** open

## Source

RBAC admin P3b whole-phase review, 2026-09-22. Deferred out of P3b: the review's other
finding (see the credential-revocation fix in this same commit) was fixed inline, this one
was declined for the phase.

## What

`AccountAdministration._creator_by_id` (`orm/eyened_orm/authz/account_admin.py:56-62`) is a
bare `session.get(Creator, creator_id)` with no `IsHuman` filter, while `AdminService.list_users`
(via `CreatorRepository.list_humans()`) filters `IsHuman.is_(True)`. `PUT /admin/users/{user_id}/password`
and `PUT /admin/users/{user_id}/active` therefore reach `creator_id` values that
`GET /admin/users` never lists: an AI-model attribution `Creator` can be given a working
`PasswordHash` and made able to log in, while never appearing in the roster an administrator
reviews.

Fix direction when picked up: filter in `AdminService.set_password`/`set_active` rather than in
`AccountAdministration._creator_by_id`, so the CLI (a trusted path with legitimate reason to
touch non-human rows) keeps its wider reach while the HTTP path returns 404.

## Why

A roster that is incomplete by construction lets an administrator grant login credentials to a
row they cannot see, which is a bigger gap than an endpoint simply missing a filter.
