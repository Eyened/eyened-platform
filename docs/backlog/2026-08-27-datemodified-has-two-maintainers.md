# `DateModified` is maintained twice once the database declares it

- **Source:** Descoped from PR #222 during design, 2026-08-27. See
  [design spec](../superpowers/specs/2026-08-27-server-default-declaration-design.md).
- **Blocked on:** nothing. It only makes sense *after* #222 lands the
  `ON UPDATE CURRENT_TIMESTAMP` declarations, since that is what makes the
  Python-side mechanism redundant.

---

## 1. Remove the redundant Python-side `onupdate` from the four models that have it

**Status:** open

**What:** Four models declare `mapped_column(onupdate=func.now())` on
`DateModified`:

| Model | Site |
|---|---|
| `AnnotationData` | `orm/eyened_orm/annotation.py:146` |
| `FormAnnotation` | `orm/eyened_orm/form_annotation.py:83` |
| `ImageInstance` | `orm/eyened_orm/image_instance.py:179` |
| `ImageStorage` | `orm/eyened_orm/image_instance.py:404` |

After #222 the same five columns carry
`server_default=CurrentTimestampOnUpdate()` plus `server_onupdate=FetchedValue()`,
so the database maintains them for every writer on MySQL. The Python-side `onupdate` becomes a second mechanism doing the same
job. Drop it, leaving the database as the single maintainer, and keep
`server_onupdate=FetchedValue()` so the ORM still expires the attribute.

**Why it is not a behaviour change today:** with the Python-side `onupdate`
present, SQLAlchemy names `DateModified` explicitly in every `UPDATE` it emits.
MySQL only auto-updates a column a statement leaves alone, so the DDL clause
never fires for ORM writes — both paths write the same instant. The columns are
correct either way; what is wrong is that a reader cannot tell which mechanism
is authoritative, and the next model to be added will copy whichever it happens
to see.

**Why it was deferred:** removing it changes what the ORM emits in an `UPDATE`,
which touches flush semantics in every repository that flushes and serialises
inside the request transaction — `form_annotation_repository.save()` documents
exactly this dependency. Measured during #222's design: after a `flush()` with
no commit, a column with `server_default` alone serves a **stale** value
(`11:20:48` returned while the row held `11:20:49`); with
`server_onupdate=FetchedValue()` it does not. So the removal is very likely
safe, but "very likely" is not the standard for a change that silently alters
what an API returns, and #222 was already large.

**Done when:** the four `onupdate=func.now()` declarations are gone; a test per
affected repository pins that a flush-only transaction serialises the value the
database actually holds; the suite is green.

## 2. Decide whether `Segmentation.Inactive` and `FormAnnotation.Inactive` want DDL defaults

**Status:** open, low priority

**What:** `ImageInstance.Inactive` and `ImageStorage.IsPrimary` carry DDL
defaults on dev (`DEFAULT '0'` / `DEFAULT '1'`); `Segmentation.Inactive` and
`FormAnnotation.Inactive` are `NOT NULL` with no default. #222 matches dev
exactly rather than harmonising, so the inconsistency survives.

**Why deferred:** adding a default to the latter two is a change to the database
rather than a correction of drift, and nothing currently fails because of it —
every writer names the column. Worth deciding deliberately rather than as a
side effect of a drift fix.
