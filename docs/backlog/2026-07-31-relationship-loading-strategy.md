# Relationship loading has three inconsistent treatments — and `Tag`'s reverse collections want the third

**Status:** open

## Source

Surfaced during the 2026-07-31 python-development review of the RBAC P2.1 fix plan
([`docs/superpowers/plans/2026-07-31-rbac-p2-1-review-fixes.md`](../superpowers/plans/2026-07-31-rbac-p2-1-review-fixes.md),
Tasks 4 and 5), while deciding whether `StudyRepository.get_tag` should use
`noload` or `raiseload`. The narrow question turned out to be a symptom. All
counts and behaviours below were verified against the tree on 2026-07-31, not
inferred.

## What

### The inconsistency

The repo has **42 `lazy="selectin"` relationships** across 9 model files —
`tag.py` 11, `image_instance.py` 10, `segmentation.py` 8, `annotation.py` 4,
`study.py` 3, `patient.py` 2, `series.py` 2, `creator.py` 1,
`form_annotation.py` 1 — against roughly **20 bare `session.get(Model, …)` calls
with no options** in the repositories. Every one of those fans out into all of
that model's selectin collections.

Three different treatments coexist, with no stated convention:

1. **Mapper-level `lazy="noload"`** — `StorageBackend.ImageStorages`
   (`image_instance.py:110-114`) and `AttributeDefinition.AttributeValues`
   (`attributes.py:154-158`). Always on, no call site can forget it.
2. **Per-query `noload()` lists** — `TagRepository.get_by_id` and `list_all`
   (`tag_repository.py`), 12 calls, the six-line list duplicated verbatim in both.
   P2.1 Task 4 factors this into a `TAG_LINK_COLLECTIONS` constant and Task 5
   adds a third consumer.
3. **Nothing** — the other ~20 bare `get`s.

### The concrete change

**Declare `Tag`'s six link collections `lazy="noload"` at the mapper**
(`tag.py:65-101`), matching treatment (1), and delete treatment (2) entirely.

The precondition holds: **nothing in the codebase reads them.** Verified by
grepping non-test `orm/` and `server/` for `.CreatorTagLinks`,
`.StudyTagLinks`, `.ImageInstanceTagLinks`, `.AnnotationTagLinks`,
`.SegmentationTagLinks` and `.FormAnnotationTagLinks` — every hit is either one
of the `noload()` calls that suppress them, or the **opposite direction**
(`ImageInstance.ImageInstanceTagLinks`, `Study.StudyTagLinks`,
`Segmentation.SegmentationTagLinks`, `FormAnnotation.FormAnnotationTagLinks`),
which is the entity→its-tags read and is legitimately `selectinload`ed in
`image_instance_repository.py`, `form_annotation_repository.py`,
`segmentation_repository.py` and `search/selects.py`. The tag→all-entities-
carrying-it direction has no reader at all.

This is the same shape as the two existing mapper-level cases: a small shared
lookup row with unbounded reverse fan-in that nobody enumerates.

## Why

Three payoffs, in increasing order of importance.

**It removes the duplication.** Two verbatim six-line lists with nothing keeping
them in sync, plus the constant P2.1 introduces to manage them, all become
unnecessary.

**It removes a real cost.** `ImageInstanceTag` holds 86,190 rows on the dev
database and the worst single tag accounts for 76,647 of them, all materialised
as ORM objects by any bare `session.get(Tag, …)`.

**It closes the hole P2.1 cannot.** `session.get()` **silently ignores its
`options` on an identity-map hit**, so a per-query `noload` protects only a
fresh load. P1's `RESTRICT`→409 behaviour therefore rests on an unenforced
invariant: that no request loads a `Tag` before calling `delete_tag`. A loaded
link collection makes the ORM's dependency processor try to blank a primary-key
column on delete, raising `AssertionError` **before any SQL** — pre-empting the
foreign key and turning the intended 409 back into a 500. A mapper-level
`lazy="noload"` has no such gap: the collections are never loaded by any path,
so there is nothing in the identity map to pre-empt them.

Note this hazard is **specific to the six `*TagLink` tables**, whose primary keys
contain `TagID`. The two existing `lazy="noload"` relationships are *not*
instances of it — `ImageStorage` and `AttributeValue` both use surrogate
single-column PKs (`image_instance.py:141`, `attributes.py:249`), so the FK is
not part of the target's PK and the assertion cannot arise. They are pure
fan-out guards. `Tag` is the case where both motivations coincide.

**Risk if left undone:** the duplication drifts, and P4/P5 — which add writes to
the same request as a tag delete — can re-arm the 500 simply by loading a `Tag`
earlier in the request, with no test able to see it coming.

## Sub-question: `noload` vs `raiseload`

Considered and deferred with this item rather than settled piecemeal.

`noload` returns a *silently wrong* collection. Measured: after
`study_service.py:57` does `link.Tag = tag`, `tag.StudyTagLinks` reports **1 of
2 real rows** — a plausible-looking half-truth. `raiseload` turns the same access
into a loud `InvalidRequestError`. The obvious objection is empirically false:
`link.Tag = tag` followed by `session.flush()` works fine under `raiseload`,
because the backref append uses `PASSIVE_NO_FETCH` and fires no lazy load.

P2.1 kept `noload` deliberately, for consistency with the two `TagRepository`
methods — having the same six collections behave differently depending on which
repository loaded the `Tag` is worse than the half-truth. That reasoning
dissolves if the strategy moves to the mapper, where there is exactly one
declaration: decide `noload` vs `raiseload` **once**, there.

## Sequencing / verification burden

Not a drive-by change. Before it lands:

- P2.1's new tests in Tasks 4 and 5 assert on `fetched.StudyTagLinks` being
  empty. Under a mapper-level `noload` those become **vacuous** (always empty)
  and must be rewritten — under `raiseload` they would instead assert the raise.
  The existing `test_get_by_id_does_not_load_the_link_collections`
  (`test_tag_repository.py:119`) has the same problem.
- Confirm no test relies on reading the collections to set up or assert
  (several do, and they are the reason the grep above was restricted to
  non-test code).
- Confirm the `link.Tag = tag` backref append still works under whichever
  directive is chosen — expected yes, `PASSIVE_NO_FETCH`, but worth pinning with
  a test since the whole tag-application path depends on it.
- P2.1's `TAG_LINK_COLLECTIONS` constant and its mapper-derived coverage test
  become dead and should be removed in the same change, not left orphaned.

The broader question — whether the other ~20 bare `session.get`s need attention —
is **probably no**, and should not expand this item. `Tag` is pathological
because it is a shared lookup row with unbounded fan-in; `ImageInstance` has more
selectin relationships but each is per-image and bounded. Fan-out severity tracks
the cardinality of the reverse collection, not the count of relationships.
