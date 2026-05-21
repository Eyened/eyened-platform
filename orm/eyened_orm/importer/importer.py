from __future__ import annotations

from collections import defaultdict
from graphlib import CycleError, TopologicalSorter
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy.orm import Session
from eyened_orm.base import Base

from .import_run import ImportRun, Update
from .importer_dtos import ImportRow
from .importer_mappings_base import Entity, Lookup, LookupPart
from .importer_mappings_image import ENTITY_SPECS
from .preparation import PreparationOptions, prepare_rows


def entity_build_order(entity_specs: tuple[Entity, ...]) -> tuple[Entity, ...]:
    """
    Topological order: every ``implies`` parent appears before its child.

    ``entity_specs`` must list every entity that appears as an implication parent.
    """
    spec_set = set(entity_specs)
    graph: dict[Entity, frozenset[Entity]] = {}
    for entity in entity_specs:
        parents = frozenset({imp.parent for imp in entity.implies})
        missing = set(parents) - spec_set
        if missing:
            names = ", ".join(sorted(e.name for e in missing))
            raise RuntimeError(
                f"Entity {entity.name!r} implies parent(s) not in entity_specs: {names}"
            )
        graph[entity] = parents
    ts = TopologicalSorter(graph)
    try:
        return tuple(ts.static_order())
    except CycleError as e:
        raise RuntimeError("Cycle in entity implies graph (cannot build order)") from e


def build_image_import_rows(
    rows: Sequence[ImportRow],
    *,
    defaults: Optional[dict[str, Any]] = None,
    infer_storage_format: bool = True,
    options: Optional[PreparationOptions] = None,
) -> list[ImportRow]:
    """
    Turn raw :class:`~eyened_orm.importer.importer_dtos.ImportRow` inputs into
    rows ready for :func:`plan_import` (defaults, optional format inference, …).

    Pass ``options`` for full control; otherwise ``defaults`` and
    ``infer_storage_format`` build a :class:`~eyened_orm.importer.preparation.PreparationOptions`.
    """
    if options is not None:
        return prepare_rows(rows, options=options)
    return prepare_rows(
        rows,
        options=PreparationOptions(
            infer_image_format=infer_storage_format,
            defaults=defaults,
        ),
    )


def plan_image_import(
    session: Session,
    rows: Sequence[ImportRow],
    *,
    defaults: Optional[dict[str, Any]] = None,
    infer_storage_format: bool = True,
    entity_specs: tuple[Entity, ...] = ENTITY_SPECS,
    options: Optional[PreparationOptions] = None,
) -> ImportRun:
    """Prepare image rows, then :func:`plan_import` (same defaults / inference knobs as :func:`build_image_import_rows`)."""
    prepared = build_image_import_rows(
        rows,
        defaults=defaults,
        infer_storage_format=infer_storage_format,
        options=options,
    )
    return plan_import(session, prepared, entity_specs=entity_specs)


def plan_import(
    session: Session,
    rows: Sequence[Any],
    *,
    entity_specs: tuple[Entity, ...] = ENTITY_SPECS,
) -> ImportRun:
    """
    Plan creates/updates for ``rows`` against ``entity_specs``.

    Image rows should normally be built with :func:`build_image_import_rows` or
    planned in one step via :func:`plan_image_import`. Task imports pass
    :class:`~eyened_orm.importer.importer_dtos.ImportTaskRow` sequences and
    ``entity_specs=TASK_ENTITY_SPECS``.
    """
    prepared = list(rows)

    build_order = entity_build_order(entity_specs)
    cache = Cache(entity_specs)
    run = ImportRun(session=session)

    seeder = Seeder(session, prepared, cache, build_order)
    seeder.seed()

    builder = Builder(prepared, cache, build_order)
    builder.build(run)
    return run


class Cache:
    def __init__(self, entity_specs: tuple[Entity, ...]):
        self.entity_specs = entity_specs
        self.by_entity: dict[Entity, dict[Any, Base]] = {
            entity_cls: {} for entity_cls in entity_specs
        }

    def _for_entity(self, entity: Entity) -> dict[Any, Base]:
        return self.by_entity[entity]

    def get(self, entity: Entity, row: Any) -> Base | None:
        return self._for_entity(entity).get(row)

    def set(self, entity: Entity, row: Any, obj: Base) -> None:
        self._for_entity(entity)[row] = obj

    def lookup_natural(
        self, entity: Entity, row: Any
    ) -> tuple[Lookup, Any] | None:
        return self._first_lookup(entity, row, resolve_column=False)

    def lookup_db(self, entity: Entity, row: Any) -> tuple[Lookup, Any] | None:
        return self._first_lookup(entity, row, resolve_column=True)

    def _resolve_lookup_part(
        self,
        entity: Entity,
        part: LookupPart,
        row: Any,
        *,
        resolve_column: bool,
    ) -> Any | None:
        if part.source is None:
            return getattr(row, entity.fields[part.column], None)

        parent_obj = self.get(part.source, row)
        if parent_obj is None:
            return None
        if resolve_column:
            return getattr(parent_obj, part.column, None)
        return parent_obj

    def _resolve_lookup(
        self,
        entity: Entity,
        lookup: Lookup,
        row: Any,
        *,
        resolve_column: bool,
    ) -> Any | None:
        values = tuple(
            self._resolve_lookup_part(
                entity,
                part,
                row,
                resolve_column=resolve_column,
            )
            for part in lookup.parts
        )
        if any(v is None for v in values):
            return None
        return values[0] if len(values) == 1 else values

    def _first_lookup(
        self,
        entity: Entity,
        row: Any,
        *,
        resolve_column: bool,
    ) -> tuple[Lookup, Any] | None:
        for lookup in entity.lookups:
            values = self._resolve_lookup(
                entity,
                lookup,
                row,
                resolve_column=resolve_column,
            )
            if values is not None:
                return lookup, values
        return None

    def seed(self, entity: Entity, row: Any, obj: Base) -> None:
        # store the object in the cache
        # also traverse the implied entities and store them in the cache
        # e.g. if seeding a Study, also seed the Patient and Project recursively
        existing = self.get(entity, row)
        if existing is not None:
            if existing is obj:
                return
            raise RuntimeError(
                (
                    f"Conflicting {entity.name} resolved",
                    f"{existing} vs {obj}",
                    f"row: {row}",
                )
            )
        self.set(entity, row, obj)

        for imp in entity.implies:
            implied_obj = getattr(obj, imp.attribute, None)
            if implied_obj is None:
                if imp.required:
                    raise RuntimeError(f"missing parent {imp.parent.name} for row")
                continue
            self.seed(imp.parent, row, implied_obj)


class Seeder:
    def __init__(
        self,
        session: Session,
        data: Sequence[Any],
        cache: Cache,
        build_order: tuple[Entity, ...],
    ):
        self.session = session
        self.data = data
        self.cache = cache
        self.build_order = build_order

    def fetch(
        self, model: type[Base], key_columns: str | tuple[str, ...], keys: Iterable[Any]
    ):
        if not keys:
            return {}
        return model.fetch_dict(self.session, key_columns=key_columns, keys=keys)

    def seed(self) -> None:
        for entity in reversed(self.build_order):
            # Building bottom up allows seeding of existing parents via implied entities.
            # For example: fetching an existing Series, Study, Patient, Project etc via ImageInstance.
            # This ensures that existing relationships are preserved and inconsistencies are detected.
            # For instance, if both a Series and an ImageInstance are identified in the same row,
            # they should already be linked in the database (i.e., we cannot update an ImageInstance belonging to another Series).
            self.seed_existing_rows(entity)
        for entity in self.build_order:
            self.seed_existing_rows(entity)

    def scan_rows(self, entity: Entity) -> tuple[
        dict[Any, list[Any]],
        dict[Lookup, dict[Any, list[Any]]],
    ]:
        pk_values = defaultdict(list)
        lookup_values = {lookup: defaultdict(list) for lookup in entity.lookups}

        for row in self.data:
            if self.cache.get(entity, row) is not None:
                continue

            pk_value = getattr(row, entity.pk_row_field)
            if pk_value is not None:
                pk_values[pk_value].append(row)
                # don't check lookups for rows with a primary key
                continue

            resolved_lookup = self.cache.lookup_db(entity, row)
            if resolved_lookup is not None:
                lookup, lookup_value = resolved_lookup
                lookup_values[lookup][lookup_value].append(row)

        return pk_values, lookup_values

    def seed_existing_rows(self, entity: Entity) -> None:
        pk_values, lookup_values = self.scan_rows(entity)
        by_pk = self.fetch(
            entity.model,
            key_columns=entity.pk_column,
            keys=pk_values.keys(),
        )
        # retrieve existing objects by primary key
        for pk_value, rows in pk_values.items():
            obj = by_pk.get(pk_value)
            if obj is None:
                raise RuntimeError(
                    f"Primary key {pk_value} for {entity.name} not found in the database"
                )
            for row in rows:
                self.cache.seed(entity, row, obj)

        # retrieve existing objects by lookup
        # e.g. Series via SeriesInstanceUID or Patient via (Project + PatientIdentifier)
        for lookup, grouped_rows in lookup_values.items():
            by_lookup = self.fetch(
                entity.model,
                key_columns=lookup.columns,
                keys=grouped_rows.keys(),
            )
            for lookup_value, rows in grouped_rows.items():
                obj = by_lookup.get(lookup_value)
                if obj is None:
                    # these will have to be created
                    continue
                for row in rows:
                    self.cache.seed(entity, row, obj)


class Builder:
    def __init__(
        self,
        data: Sequence[Any],
        cache: Cache,
        build_order: tuple[Entity, ...],
    ):
        self.cache = cache
        self.data = data
        self.build_order = build_order

    def attach_parents(
        self, entity: Entity, row: Any, obj: Base
    ) -> dict[str, Update]:
        result = {}
        for imp in entity.implies:
            parent = self.cache.get(imp.parent, row)
            if parent is None:
                if imp.required:
                    raise RuntimeError(
                        f"Missing parent {imp.parent.name} for {entity.name}"
                    )
                continue
            result[imp.attribute] = Update(old_value=None, new_value=parent)
            setattr(obj, imp.attribute, parent)
        return result

    def get_updates(
        self, entity: Entity, row: Any, obj: Base
    ) -> dict[str, Update]:
        updates = {}
        for orm_field, row_field in entity.fields.items():
            if orm_field in entity.non_mutable:
                continue
            new_value = getattr(row, row_field, None)
            if new_value is None:
                continue
            old_value = getattr(obj, orm_field, None)
            if old_value == new_value:
                continue
            updates[orm_field] = Update(old_value=old_value, new_value=new_value)
            setattr(obj, orm_field, new_value)
        return updates

    def build_key(self, entity: Entity, row: Any) -> tuple[Any, ...]:
        resolved_lookup = self.cache.lookup_natural(entity, row)
        if resolved_lookup is not None:
            # identity is defined by the lookup key
            lookup, lookup_value = resolved_lookup
            return (entity, "lookup", lookup.columns, lookup_value)

        anonymous_field = entity.anonymous_identity
        if anonymous_field is None:
            # In case we want to strictly enforce that all entities are created, we should raise here
            # Current behaviour is that we skip the entity if we can't build it
            # If it turns out that this entity is required somewhere else, that will trigger an error later
            return None
            raise RuntimeError(
                f"Cannot build {entity.name} without either {entity.pk_row_field} "
                f"or a complete lookup key"
            )

        # anonymous identity can be used for grouping rows
        # for example, to create multiple ImageInstances for the same Series
        # even when series_instance_uid is absent
        anonymous_identity = getattr(row, anonymous_field, None)
        if anonymous_identity is None:
            required_implies = [imp for imp in entity.implies if imp.required]
            if not required_implies or any(
                self.cache.get(imp.parent, row) is None for imp in required_implies
            ):
                # if we're about to create an anonymous per-row entity,
                # but required parents weren't built for this row, just skip it
                return None

            # this effectively creates a new entity for the row
            return (entity, "row", id(row))
            
        parent_scope = tuple(
            self.cache.get(imp.parent, row)
            for imp in entity.implies
            if imp.required
        )
        return (entity, "group", anonymous_identity, parent_scope)

    def build_entity(self, entity: Entity, import_run: ImportRun) -> None:
        # local cache for deduplication
        created_by_key: dict[tuple[Any, ...], Base] = {}

        for row in self.data:
            obj = self.cache.get(entity, row)
            created = False
            updates = {}
            if obj is None:
                key = self.build_key(entity, row)
                if key is None:
                    continue
                obj = created_by_key.get(key)
                if obj is None:
                    obj = entity.model()
                    parent_updates = self.attach_parents(entity, row, obj)
                    updates.update(parent_updates)
                    created_by_key[key] = obj
                    created = True
                self.cache.seed(entity, row, obj)
            field_updates = self.get_updates(entity, row, obj)
            updates.update(field_updates)
            if created:
                import_run.add_create(obj, updates)
            elif updates:
                import_run.add_update(obj, updates)
            else:
                # no updates to apply
                pass

    def build(self, import_run: ImportRun) -> None:
        for entity in self.build_order:
            self.build_entity(entity, import_run)
