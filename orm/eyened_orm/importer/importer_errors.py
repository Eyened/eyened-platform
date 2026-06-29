from __future__ import annotations

from typing import Any, Protocol

from .importer_mappings_base import Entity


class _LookupCache(Protocol):
    def get(self, entity: Entity, row: Any) -> Any | None: ...

    def lookup_natural(self, entity: Entity, row: Any) -> Any | None: ...


def direct_missing_lookup_fields(entity: Entity, row: Any) -> list[str]:
    """Row fields that are part of a lookup but absent on ``row``."""
    missing: set[str] = set()
    for lookup in entity.lookups:
        for part in lookup.parts:
            if part.source is None:
                field = entity.fields[part.column]
                if getattr(row, field, None) is None:
                    missing.add(field)
    return sorted(missing)


def _lookup_source_hint(cache: _LookupCache, entity: Entity, row: Any) -> str | None:
    """One-hop hint from declared lookup keys (direct fields or lookup parent)."""
    missing = direct_missing_lookup_fields(entity, row)
    if missing:
        return f"provide row field(s): {', '.join(missing)}"

    for lookup in entity.lookups:
        for part in lookup.parts:
            if part.source is None:
                continue
            if cache.get(part.source, row) is not None:
                continue
            sub = direct_missing_lookup_fields(part.source, row)
            if sub:
                return f"provide row field(s): {', '.join(sub)}"
    return None


def missing_parent_error(
    cache: _LookupCache,
    *,
    entity: Entity,
    parent: Entity,
    row: Any,
) -> RuntimeError:
    """
    Explain why a required parent entity is not available for ``row``.

    For parents that can be created without a natural key (``anonymous_identity``),
    explains missing grandparents instead of unrelated lookup fields such as
    ``sop_instance_uid``.
    """
    has_natural_key = cache.lookup_natural(parent, row) is not None
    if parent.anonymous_identity is not None and not has_natural_key:
        for imp in parent.implies:
            if not imp.required or cache.get(imp.parent, row) is not None:
                continue
            hint = _lookup_source_hint(cache, imp.parent, row)
            if hint:
                return RuntimeError(
                    f"Cannot create {entity.name}: cannot resolve {parent.name} "
                    f"(requires {imp.parent.name}); {hint}"
                )
        return RuntimeError(
            f"Cannot create {entity.name}: missing required parent {parent.name}"
        )

    hint = _lookup_source_hint(cache, parent, row)
    if hint:
        return RuntimeError(
            f"Cannot create {entity.name}: cannot resolve {parent.name}; {hint}"
        )
    return RuntimeError(
        f"Cannot create {entity.name}: missing required parent {parent.name}"
    )
