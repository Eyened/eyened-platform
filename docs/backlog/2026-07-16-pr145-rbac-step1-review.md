# Follow-ups from PR #145 — RBAC Step 1 service layer

- **Source:** [PR #145 review by @bjliefers](https://github.com/Eyened/eyened-platform/pull/145#pullrequestreview-4712228703) (Approved with follow-ups, 2026-07-16)
- **Verdict:** Approve with follow-ups. "Solid migration — thin routes, injected services, testable repositories. Matches the Step 1 spec."
- **Related spec:** [Repository / service layer design](../superpowers/specs/2026-07-03-repository-service-layer-design.md)

The reviewer flagged these as optimization follow-ups to handle in a **separate round**,
not blockers for merge. They are related and worth tackling together, ideally **before
Step 2 adds more call sites**.

---

## 1. Repository eager-loading convention

**Status:** open

**What:** Pick one convention for eager loading in repositories. Several repos bake in
`selectinload` graphs copied from the old route handlers
(`FormAnnotationRepository.list_active`, `SegmentationRepository.get_with_tag_links`, etc.),
while others expose flags (`ImageInstanceRepository`, `PatientRepository.get_with_attributes`).

**Why:** Establish one convention before Step 2 adds more call sites. Baked-in
`selectinload` may not be sustainable once we want advanced access-control filtering
(e.g. only Tags exposed to the requesting user, not all tags in the database) — a blanket
`selectinload` just selects all related entities.

> Verbatim: "Several repos bake in `selectinload` graphs copied from old route handlers
> (`FormAnnotationRepository.list_active`, `SegmentationRepository.get_with_tag_links`,
> etc.), while others expose flags (`ImageInstanceRepository`,
> `PatientRepository.get_with_attributes`). Worth picking one convention before Step 2
> adds more call sites. If we want to do advanced filtering in the future (e.g. only Tags
> exposed to the user that does the fetch, not all tags in the database) the selectinload
> may not be sustainable (that will just select all related entities I think)."

---

## 2. Dead eager loads

**Status:** open

**What:** Remove eager loads whose results are never used. Form-annotation and
segmentation GET/list still call the DTO converter with `with_tag_metadata=False`, so
tag links are fetched but `tags` stays `[]`.

**Why:** Wasted queries. Related to how DTO converters map ORM objects to API responses —
their input should be **explicit**, not derived by iterating through ORM relationships.

> Verbatim: "In a few places the loaded associations are not used: form-annotation and
> segmentation GET/list still call the DTO converter with `with_tag_metadata=False`, so
> tag links are fetched but `tags` stays `[]`."
>
> "Perhaps follow up on those in a separate round. This is mainly about optimization, but
> we may need to evaluate again how to formulate the queries in the repository layer,
> perhaps the selectinload is not (or not always) appropriate. Related to how the
> DTO-converters convert ORM objects to API responses: their input should be explicit,
> not by iterating through ORM relationships."
