from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import json
import logging
from pathlib import Path
from typing import Any
import uuid

from sqlalchemy.orm import Session

from eyened_orm.base import Base

from eyened_orm.image_instance import ImageInstance
from eyened_orm.utils.table_printer import format_table_html


def _serialize(value: Any) -> Any:
    if isinstance(value, Base):
        return {
            "type": "entity",
            "entity_model": value.__class__.__name__,
            "primary_key": {
                col.name: getattr(value, col.name) for col in value.primary_keys()
            },
        }
    elif isinstance(value, Enum):
        # Ensure JSON-serializable primitive (no custom encoder required).
        # Prefer the Enum's `.value` when possible.
        enum_value = value.value
        if isinstance(enum_value, (str, int, float, bool)) or enum_value is None:
            return {
                "type": "value",
                "value": enum_value,
            }
        return {
            "type": "value",
            "value": str(enum_value),
        }
    elif isinstance(value, (datetime, date)):
        # Use ISO format for stable JSON representation.
        return {
            "type": "value",
            "value": value.isoformat(),
        }
    else:
        return {
            "type": "value",
            "value": value,
        }


def _deserialize(session: Session, d: dict[str, Any]) -> Any:
    if d["type"] == "entity":
        model = _resolve_model_by_name(d["entity_model"])
        result = model.by_column(session, **d["primary_key"])
        if result is None:
            logging.warning(
                f"Entity {model.__name__} not found for primary key: {d['primary_key']}"
            )
        return result
    elif d["type"] == "value":
        return d["value"]
    else:
        raise ValueError(f"Unknown import update type: {d['type']}")


@dataclass
class Update:
    old_value: Any
    new_value: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_value": _serialize(self.old_value),
            "new_value": _serialize(self.new_value),
        }

    @classmethod
    def from_dict(cls, session: Session, d: dict[str, Any]) -> Update:
        return cls(
            old_value=_deserialize(session, d["old_value"]),
            new_value=_deserialize(session, d["new_value"]),
        )


def _resolve_model_by_name(entity_name: str) -> type[Base]:
    """return the model class for the given entity name
    e.g. "Project" -> Project
    """
    reg = Base.registry._class_registry  # type: ignore[attr-defined]
    model = reg.get(entity_name)
    if model is None or not isinstance(model, type) or not issubclass(model, Base):
        raise ValueError(f"Unknown entity_name in ImportChange: {entity_name!r}")
    return model


class ImportUpdate:

    name = "UPDATE"

    def __init__(self, entity: Base, updates: dict[str, Update]):
        self.entity = entity
        self.updates = updates

    @property
    def primary_key(self):
        pk_cols = self.entity.__class__.primary_keys()
        return {c.name: getattr(self.entity, c.name) for c in pk_cols}

    def apply(self, session):
        for col_name, update in self.updates.items():
            setattr(self.entity, col_name, update.new_value)

    def undo(self, session):
        for col_name, update in self.updates.items():
            setattr(self.entity, col_name, update.old_value)

    def summary(self) -> str:
        def format_value(value: Any) -> str:
            if isinstance(value, Base):
                pk_val = ", ".join(
                    f"{col.name}={getattr(value, col.name)}"
                    for col in value.primary_keys()
                )
                return f"{value.__class__.__name__} ({pk_val})"
            return str(value)

        result = [f"{self.name} {format_value(self.entity)}"]
        max_col_len = max((len(col_name) for col_name in self.updates), default=0)
        for col_name, update in self.updates.items():
            result.append(
                f"  {col_name:<{max_col_len}} : {format_value(update.old_value)} -> {format_value(update.new_value)}"
            )

        return "\n".join(result) + "\n"

    def to_dict(self):
        return {
            "type": "update",
            "entity": _serialize(self.entity),
            "updates": {k: v.to_dict() for k, v in self.updates.items()},
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any], session) -> ImportUpdate:
        return cls(
            entity=_deserialize(session, d["entity"]),
            updates={k: Update.from_dict(session, v) for k, v in d["updates"].items()},
        )


class ImportCreate(ImportUpdate):

    name = "CREATE"

    def apply(self, session):
        session.add(self.entity)
        super().apply(session)

    def undo(self, session):
        session.delete(self.entity)

    def to_dict(self):
        result = super().to_dict()
        result["type"] = "create"
        return result


def parse_import_update(d: dict[str, Any], session: Session) -> ImportUpdate:
    if d["type"] == "update":
        return ImportUpdate.from_dict(d, session)
    elif d["type"] == "create":
        return ImportCreate.from_dict(d, session)
    else:
        raise ValueError(f"Unknown import update type: {d['type']}")


def color_fundus_image_ids_from_import_run(import_run: ImportRun) -> list[int]:
    """Collect ``ImageInstanceID``s for ColorFundus images created in this run.

    Only considers ``ImportCreate`` changes whose entity is an ``ImageInstance``.
    Use after ``apply()`` (and typically after IDs are flushed) so PKs are set.
    """
    from eyened_orm import ImageInstance
    from eyened_orm.image_instance import Modality

    ids: list[int] = []
    for change in import_run.changes:
        if not isinstance(change, ImportCreate):
            continue
        if not isinstance(change.entity, ImageInstance):
            continue
        if change.entity.Modality == Modality.ColorFundus:
            ids.append(change.entity.ImageInstanceID)
    return ids


class ImportRun:
    def __init__(
        self,
        session: Session,
        import_run_id: str = None,
        status: str = "pending",
    ):
        self.session = session
        self.import_run_id = import_run_id or uuid.uuid4().hex
        self.status = status
        self.changes = []

    def apply(self) -> None:
        """
        Apply the changes to the database.
        Flushes the changes to the database, but does not commit the transaction.
        """
        try:
            self.session.add_all([change.entity for change in self.changes])

            with self.session.begin_nested():
                for change in self.changes:
                    change.apply(self.session)
                self.session.flush()
                self.status = "done"
        except Exception:
            self.status = "failed"
            raise

    def undo(self) -> None:
        """
        Undo the changes to the database.
        Flushes the changes to the database, but does not commit the transaction.
        """
        if self.status != "done":
            raise RuntimeError(
                f"Cannot undo import: run status is {self.status!r}, expected 'done'"
            )
        try:
            self.session.add_all([change.entity for change in self.changes])
            with self.session.begin_nested():
                for change in reversed(self.changes):
                    change.undo(self.session)
                self.session.flush()
                self.status = "cancelled"
        except Exception:
            self.status = "failed"
            raise

    def get_new_images(self) -> list[ImageInstance]:
        return [
            change.entity
            for change in self.changes
            if isinstance(change, ImportCreate)
            and isinstance(change.entity, ImageInstance)
        ]

    def add_update(self, entity: Base, updates: dict[str, Update]):
        update = ImportUpdate(entity=entity, updates=updates)
        self.changes.append(update)

    def add_create(self, entity: Base, updates: dict[str, Update]):
        create = ImportCreate(entity=entity, updates=updates)
        self.changes.append(create)

    def to_dict(self) -> dict[str, Any]:
        return {
            "import_run_id": self.import_run_id,
            "status": self.status,
            "changes": [c.to_dict() for c in self.changes],
        }

    @classmethod
    def from_dict(cls, session: Session, d: dict[str, Any]) -> "ImportRun":
        run = cls(
            session=session,
            import_run_id=d["import_run_id"],
            status=d.get("status", "unknown"),
        )
        run.changes = [parse_import_update(c, session) for c in d.get("changes", [])]

        return run

    def write_json(self, path: str | Path) -> Path:
        if self.status != "done":
            logging.warning(
                f"Import run {self.import_run_id} is not done"
                f"Some database keys may not be present in the file"
                f"Loading may fail to resolve all entities"
            )
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        return path

    @classmethod
    def read_json(cls, session: Session, path: str | Path) -> "ImportRun":
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            return cls.from_dict(session, json.load(f))

    def full_summary(self) -> str:
        lines = [
            f"Import run {self.import_run_id}",
            f"Status: {self.status}",
            f"Change count: {len(self.changes)}",
        ]
        for i, change in enumerate(self.changes, 1):
            lines.append(f"{i}. {change.summary()}")
        return "\n".join(lines)

    def display_summary(self) -> None:
        per = defaultdict(lambda: {"Update": 0, "Create": 0})
        for ch in self.changes:
            name = ch.entity.__class__.__name__
            per[name]["Create" if ch.name == "CREATE" else "Update"] += 1
        rows = sorted(
            per.items(), key=lambda kv: kv[1]["Update"] + kv[1]["Create"], reverse=True
        )
        entity_data = [
            (
                entity,
                c["Update"] or "",
                c["Create"] or "",
                (c["Update"] + c["Create"]) or "",
            )
            for entity, c in rows
        ]

        from IPython.display import display, HTML

        display(
            HTML(
                f"Import run: <strong>{self.import_run_id}</strong> <br> Status: <strong>{self.status}</strong> <br> Total changes: <strong>{len(self.changes)}</strong>"
            )
        )
        headers = ["Entity", "Update", "Create", "Total"]
        display(HTML(format_table_html(headers, entity_data)))

    def print_summary(self, full: bool = False) -> None:
        if full:
            print(self.full_summary())
        else:
            print(self.summary())
