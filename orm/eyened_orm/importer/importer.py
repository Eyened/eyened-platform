from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from eyened_orm.base import Base

from .import_run import ImportRun, Update

from .importer_dtos import ImportRow
from .importer_mappings import Entity, ENTITY_SPECS


def infer_storage_format(object_key: str) -> str:
    suffix = Path(object_key).suffix.lower()
    if suffix in {".dcm", ".dicom"}:
        return "dicom"
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".mhd":
        return "mhd"
    if suffix == "":
        return "png_series"
    return "binary"


def _build_order() -> tuple[Entity, ...]:
    ordered: list[Entity] = []
    remaining = set(ENTITY_SPECS)

    while remaining:
        progress = False
        for entity in ENTITY_SPECS:
            if entity not in remaining:
                continue
            parents = {parent for parent, _ in entity.implies}
            if not parents.issubset(ordered):
                continue
            ordered.append(entity)
            remaining.remove(entity)
            progress = True
        if progress:
            continue
        unresolved = ", ".join(entity.name for entity in remaining)
        raise RuntimeError(f"Could not determine entity build order: {unresolved}")

    return tuple(ordered)


BUILD_ORDER = _build_order()
SEED_PK_ORDER = tuple(reversed(BUILD_ORDER))


def prepare_rows(
    rows: Sequence[ImportRow],
    *,
    infer_image_format: bool = True,
    defaults: Optional[dict[str, Any]] = None,
) -> list[ImportRow]:
    _defaults = defaults or {}

    prepared: list[ImportRow] = []
    for row in rows:
        updates: dict[str, Any] = {}
        if (
            infer_image_format
            and row.object_key
            and not row.image_storage_format
        ):
            updates["image_storage_format"] = infer_storage_format(row.object_key)
        for key, value in _defaults.items():
            if getattr(row, key, None) is None:
                updates[key] = value
        prepared.append(ImportRow(**{**row.model_dump(), **updates}))
    return prepared


def seed_cache(session: Session, rows: Sequence[ImportRow]) -> Cache:
    seeder = Seeder(session, rows)
    seeder.seed()
    return seeder.cache


def plan_import(
    session: Session,
    rows: Sequence[ImportRow],
    *,
    infer_storage_format: bool = True,
    defaults: Optional[dict[str, Any]] = None,
) -> ImportRun:
    prepared = prepare_rows(
        rows,
        infer_image_format=infer_storage_format,
        defaults=defaults,
    )
    cache = seed_cache(session, prepared)
    builder = Builder(prepared, cache)
    run = ImportRun(session=session)
    builder.build(run)
    return run


def run_import(
    session: Session,
    rows: Sequence[ImportRow],
    *,
    infer_image_storage_format: bool = True,
    defaults: Optional[dict[str, Any]] = None,
) -> ImportRun:
    run = plan_import(
        session,
        rows,
        infer_storage_format=infer_image_storage_format,
        defaults=defaults,
    )
    run.apply()
    return run


class Cache:
    def __init__(self, session: Session):
        self.session = session
        self.by_entity: dict[Entity, dict[ImportRow, Base]] = {
            entity_cls: {} for entity_cls in ENTITY_SPECS
        }

    def _for_entity(self, entity: Entity) -> dict[ImportRow, Base]:
        return self.by_entity[entity]

    def get(self, entity: Entity, row: ImportRow) -> Base | None:
        return self._for_entity(entity).get(row)

    def set(self, entity: Entity, row: ImportRow, obj: Base) -> None:
        self._for_entity(entity)[row] = obj

    def lookup_natural(self, entity: Entity, row: ImportRow) -> Any | None:
        return self._lookup(entity, row, resolve_column=False)

    def lookup_db(self, entity: Entity, row: ImportRow) -> Any | None:
        return self._lookup(entity, row, resolve_column=True)

    def _lookup(
        self, entity: Entity, row: ImportRow, resolve_column: bool
    ) -> Any | None:
        def get_value(part, row: ImportRow) -> Any | None:
            if part.source is None:
                field = entity.fields[part.column]
                return getattr(row, field, None)
            parent_obj = self.get(part.source, row)
            if parent_obj is None:
                return None
            if resolve_column:
                return getattr(parent_obj, part.column, None)
            else:
                return parent_obj

        values = tuple(get_value(part, row) for part in entity.lookup)
        if any(v is None for v in values):
            return None
        return values[0] if len(values) == 1 else values

    def seed(self, entity: Entity, row: ImportRow, obj: Base) -> None:
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

        for implied_entity, attr in entity.implies:
            # e.g. Patient.Project
            implied_obj = getattr(obj, attr, None)
            if implied_obj is None:
                raise RuntimeError(f"missing parent {implied_entity.name} for row")
            self.seed(implied_entity, row, implied_obj)


class Seeder:
    def __init__(self, session: Session, data: Sequence[ImportRow]):
        self.session = session
        self.data = data
        self.cache = Cache(session)

    def fetch(
        self, model: type[Base], key_columns: str | tuple[str, ...], keys: Iterable[Any]
    ):
        if not keys:
            return {}
        return model.fetch_dict(self.session, key_columns=key_columns, keys=keys)

    def seed(self) -> None:
        for entity in SEED_PK_ORDER:
            # 'bottom up' (ImageStorage -> ImageInstance -> Series -> Study -> Patient -> Project)
            self.seed_existing_rows(entity)
        for entity in BUILD_ORDER:
            # 'top down' (Project -> Patient -> Study -> Series -> ImageInstance -> ImageStorage)
            self.seed_existing_rows(entity)

    def scan_rows(self, entity: Entity) -> tuple[
        dict[Any, list[ImportRow]],
        dict[Any, list[ImportRow]],
    ]:
        pk_values = defaultdict(list)
        lookup_values = defaultdict(list)

        for row in self.data:
            if self.cache.get(entity, row) is not None:
                continue

            pk_value = getattr(row, entity.pk_row_field)
            if pk_value is not None:
                pk_values[pk_value].append(row)
                # don't check lookups for rows with a primary key
                continue

            lookup_value = self.cache.lookup_db(entity, row)
            if lookup_value is not None:
                lookup_values[lookup_value].append(row)

        return pk_values, lookup_values

    def seed_existing_rows(self, entity: Entity) -> None:
        pk_values, lookup_values = self.scan_rows(entity)
        by_pk = self.fetch(
            entity.model,
            key_columns=entity.pk_column,
            keys=pk_values.keys(),
        )
        by_lookup = self.fetch(
            entity.model,
            key_columns=entity.lookup_columns,
            keys=lookup_values.keys(),
        )
        for pk_value, rows in pk_values.items():
            obj = by_pk.get(pk_value)
            if obj is None:
                raise RuntimeError(
                    f"Primary key {pk_value} for {entity.name} not found in the database"
                )
            for row in rows:
                self.cache.seed(entity, row, obj)
        for lookup_value, rows in lookup_values.items():
            obj = by_lookup.get(lookup_value)
            if obj is None:
                # these will have to be created
                continue
            for row in rows:
                self.cache.seed(entity, row, obj)


class Builder:
    def __init__(
        self,
        data: Sequence[ImportRow],
        cache: Cache,
    ):
        self.cache = cache
        self.data = data

    def attach_parents(
        self, entity: Entity, row: ImportRow, obj: Base
    ) -> dict[str, Update]:
        result = {}
        for parent_entity, attr in entity.implies:
            parent = self.cache.get(parent_entity, row)
            if parent is None:
                raise RuntimeError(
                    f"Missing parent {parent_entity.name} for {entity.name}"
                )
            result[attr] = Update(old_value=None, new_value=parent)
            setattr(obj, attr, parent)
        return result

    def get_updates(
        self, entity: Entity, row: ImportRow, obj: Base
    ) -> dict[str, Update]:
        updates = {}
        for orm_field, row_field in entity.fields.items():
            new_value = getattr(row, row_field, None)
            if new_value is None:
                continue
            old_value = getattr(obj, orm_field, None)
            if old_value == new_value:
                continue
            updates[orm_field] = Update(old_value=old_value, new_value=new_value)
            setattr(obj, orm_field, new_value)
        return updates

    def build_key(self, entity: Entity, row: ImportRow) -> tuple[Any, ...]:
        lookup_value = self.cache.lookup_natural(entity, row)
        if lookup_value is not None:
            # identity is defined by the lookup key
            return (entity, "lookup", lookup_value)

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
            if not entity.implies or any(
                self.cache.get(parent_entity, row) is None
                for parent_entity, _ in entity.implies
            ):
                # if we're about to create an anonymous per-row entity,
                # but required parents weren't built for this row, just skip it
                return None

            # this effectively creates a new entity for the row
            return (entity, "row", id(row))
        return (entity, "group", anonymous_identity)

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
        for entity in BUILD_ORDER:
            self.build_entity(entity, import_run)
