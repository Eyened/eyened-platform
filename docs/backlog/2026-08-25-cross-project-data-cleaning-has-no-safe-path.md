# Cross-project data cleaning has no safe path, and the ORM actively misleads

**Status:** open

## Source

PR #222 review question, 2026-08-25: *"if we identify a set of misclassified
images to a specific patient/project and we need to move them to the correct
project/patient, how would that be done?"*

Answered by probe rather than by reading: the six attempts below were executed
against a throwaway **MySQL 8.0.27** — the production engine — with this
branch's schema built by `Base.metadata.create_all`, and independently against
the SQLite test harness. Identical results in both. Note that the probe used the
model metadata, **not** the migrated schema; the migrations are hand-authored and
still want a diff against the live database before they are trusted.

## What

After this branch, `ProjectID` is derived from the patient and held there by the
composite foreign key chain, so **"move these images to project X" is no longer
an expressible operation**. Only two primitives remain:

| Job | Operation |
|---|---|
| Right patient, wrong project | `UPDATE Patient SET ProjectID` — cascades all four levels |
| Wrong patient (misfiled image) | Re-point `ImageInstance.SeriesID` at a Series under the correct patient, **and set `ProjectID` in the same statement** |

Same-project re-parenting is unaffected: with source and destination series both
in project 1, updating `SeriesID` alone still satisfies
`(SeriesID, ProjectID) -> Series`. Only cross-project moves are the new case.

### Verified behaviour

| # | Attempt | Result |
|---|---|---|
| 1 | ORM: `image.SeriesID = <series in B>` | **REFUSED** — 1452 on `fk_ImageInstance_Series_Project` |
| 2 | Set `SeriesID` **and** `ProjectID`, task declares only A | **REFUSED** — 1452 on `fk_SubTaskImageLink_TaskProject` |
| 3 | `INSERT TaskProject(task,B)` first, then move | **OK** — link's `ProjectID` cascaded to B |
| 3b | `DELETE` the now-unused `TaskProject(task,A)` | **OK** |
| 4 | `UPDATE Patient SET ProjectID=B`, task declares only A | **REFUSED** — 1452 on `fk_SubTaskImageLink_TaskProject`; 0 links left violating containment |
| 5 | Declare B, then `UPDATE Patient SET ProjectID=B` | **OK** — `(patient, study, series, image, link)` all → B |
| 6 | Move a patient whose identifier already exists in B | **REFUSED** — 1062 on `ProjectIDPatientIdentifier_UNIQUE` |

Result 4 is the load-bearing one, and it is good news: InnoDB **does** re-check
the containment key when a link's `ProjectID` is rewritten by a cascade
originating four levels up on `Patient`. The design's central claim holds on the
production engine and not only in the SQLite suite, where
`test_moving_a_patient_into_an_undeclared_project_is_refused` pins it.

### The sequence that works

All DML, so it belongs in one transaction:

```sql
START TRANSACTION;
-- 1. Declare every destination project on every task the moved rows touch
INSERT INTO TaskProject (TaskID, ProjectID)
SELECT DISTINCT l.TaskID, :dest_project FROM SubTaskImageLink l
 WHERE l.ImageInstanceID IN (:images)
   AND NOT EXISTS (SELECT 1 FROM TaskProject tp
                   WHERE tp.TaskID = l.TaskID AND tp.ProjectID = :dest_project);
-- 2. Move: patient-level, or an image re-parent setting BOTH columns
UPDATE Patient SET ProjectID = :dest_project WHERE PatientID = :patient;
-- 3. Prune declarations no link uses any more
DELETE tp FROM TaskProject tp LEFT JOIN SubTaskImageLink l
       ON l.TaskID = tp.TaskID AND l.ProjectID = tp.ProjectID
 WHERE l.TaskID IS NULL AND tp.TaskID IN (:tasks);
COMMIT;
```

Step 3's targets are exactly what `unused_declarations` / `eorm
check-declarations` reports.

## Why

The constraints are right — every refusal above is the schema doing its job, and
result 4 shows containment surviving a four-level cascade. What is missing is
everything around them. Five hazards, in rough order of how likely each is to
bite:

1. **The ORM does not help and fails opaquely.** `populate_project_ids` iterates
   `session.new` only, and there is no `before_update` listener anywhere on the
   branch. An ORM-mediated re-parent therefore leaves `ProjectID` stale and dies
   on a bare foreign-key error (result 1) rather than doing the obvious right
   thing. Every future move must set both columns explicitly, or be raw SQL.

2. **Satellite tables are carried by nothing and checked by nothing.** After a
   successful move the probe left a `FormAnnotation` whose patient is in project
   1 and whose image is in project 2, with no error raised. Because scoping
   anchors `FormAnnotation` on `Patient`, that row stays visible to the *old*
   project while pointing at an image in the new one. `AttributeValue`
   (independent `PatientID`/`StudyID`/`ImageInstanceID`) and
   `Segmentation.SubTaskID` have the same shape. Any move needs a manual
   straddle sweep over these three; the composite chain guarantees nothing about
   them. This is the pre-existing `FormAnnotation` hazard PR #222 names in *What
   this doesn't fix*, reached from the other direction — a move **creates** the
   straddle rather than merely tolerating one.

3. **Pre-declaring changes visibility before anything has moved.** The set-valued
   predicate is `NOT EXISTS(a declared project outside your scope)`, so step 1
   makes the task immediately *invisible* to members of the source project only.
   Fail-safe, but a real change, and the reason steps 1–3 must not be run as
   three separate sessions.

4. **No audit trail.** `AuditLog` is written by the service layer, so a hand-SQL
   move leaves no record of arguably the most consequential change that can be
   made to access control.

5. **Identifier collisions block patient moves** (result 6) with no way to
   detect them ahead of time.

One thing that is *not* a problem: `ObjectKey` and `ThumbnailPath` are stored
columns, not derived from project or patient, so neither kind of move requires
any file or zarr movement.

## Proposed change

An `eorm move-patient` / `eorm move-images` command that:

- wraps declare → move → prune in one transaction;
- pre-checks the destination for identifier collisions and reports them before
  writing anything;
- writes `AuditLog` rows for the reassignment;
- reports the `FormAnnotation` / `AttributeValue` / `Segmentation` straddles the
  move created, so they are a visible output rather than a silent residue.

This is the concrete half of the *Declaration management* follow-up PR #222
already books: `check-declarations` can name rows whose only remediation is hand
SQL, and a move is the operation that most needs that remediation to exist.

## Related

- PR #222 — *feat(tasks): declare a task's projects instead of deriving them*.
- [`Task→project map: materialize it`](2026-08-07-task-project-materialized-map.md)
  — the performance motivation that led to the declaration.
- The `FormAnnotation` cross-project hazard is unchanged by #222 and is worth a
  separate look on its own terms; hazard 2 above is only the cleaning-time face
  of it.
