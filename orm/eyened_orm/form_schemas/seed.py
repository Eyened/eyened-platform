import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from eyened_orm.form_annotation import FormSchema

from .registry import BUILTIN_FORM_SCHEMAS, schema_path


@dataclass
class SeedResult:
    created: list[str]
    updated: list[str]
    skipped: list[str]


def _load_schema_json(schema_file: str) -> dict:
    with open(schema_path(schema_file), encoding="utf-8") as f:
        return json.load(f)


def seed_form_schemas(session: Session, *, update: bool = False) -> SeedResult:
    """Insert or optionally update builtin viewer FormSchema rows."""
    result = SeedResult(created=[], updated=[], skipped=[])

    for builtin in BUILTIN_FORM_SCHEMAS:
        schema_json = _load_schema_json(builtin.schema_file)
        existing = FormSchema.by_name(session, builtin.name)

        if existing is None:
            session.add(
                FormSchema(
                    SchemaName=builtin.name,
                    Schema=schema_json,
                    EntityType=builtin.entity_type,
                )
            )
            result.created.append(builtin.name)
            continue

        if update:
            existing.Schema = schema_json
            existing.EntityType = builtin.entity_type
            result.updated.append(builtin.name)
        else:
            result.skipped.append(builtin.name)

    session.commit()
    return result
