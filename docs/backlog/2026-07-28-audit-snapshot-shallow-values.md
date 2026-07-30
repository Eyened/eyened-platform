# `AuditService.snapshot` holds references, not copies

**Status:** open

## Source

Repository write-back design, branch `feature/rbac-step2-authz`.
Spec: `docs/superpowers/specs/2026-07-28-repository-write-back-design.md` §3.
Deferred deliberately at design time rather than discovered in review.

## What

`AuditService.snapshot(entity, *fields)` captures `getattr(entity, field)` into a
plain dict. For immutable column values (`str`, `int`, `datetime`, `Enum`) that is
a true before-image. For **mutable** column values — the JSON columns `FormData`,
`TaskConfig`, `Changes` — it captures a *reference*. If a caller mutates such a
value in place:

```python
before = AuditService.snapshot(annotation, "FormData")
annotation.FormData["answer"] = "changed"      # in-place
AuditService.diff(before, annotation)          # => {} — the change is invisible
```

`before["FormData"]` and `annotation.FormData` are the same object, so the
`old != new` comparison is false and the field is dropped from the audit record.

The fix is a value-copy at snapshot time (`copy.deepcopy`, or a narrower
copy for known-JSON columns) — with a decision on the cost of deep-copying large
`FormData` payloads on every audited write.

## Why

- **Not a regression.** The pre-existing `get_history` implementation had the
  same blind spot: SQLAlchemy does not flag in-place mutation of a plain `JSON`
  column as a change without `MutableDict`/`MutableList`. Behaviour is unchanged
  by the write-back refactor.
- **No current path relies on it.** The only service that writes a JSON column,
  `FormAnnotationService.set_value` (`server/services/form_annotation_service.py:247`),
  assigns a *new* object rather than mutating in place, and deliberately records
  no `changes` (high-frequency op, lightweight by design — preserved from
  pre-refactor `log_simple`).
- **Risk if left undone:** a future service that mutates `FormData`/`TaskConfig`
  in place gets a silently empty audit diff. Since `AuditLog.Changes` is the
  compliance sink, the loss is invisible — no exception, no failing test.

## Related

The stronger fix is to make the ORM itself detect it: declare the JSON columns
as `MutableDict.as_mutable(JSON)`. That fixes `snapshot`, dirty-tracking, and
`get_history` in one move, but changes flush behaviour for every writer of those
columns — which is why it is not folded into a write-back naming refactor.
