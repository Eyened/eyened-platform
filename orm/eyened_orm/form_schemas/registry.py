from dataclasses import dataclass
from pathlib import Path

from eyened_orm.form_annotation import EntityType

_SCHEMA_DIR = Path(__file__).parent


@dataclass(frozen=True)
class BuiltinFormSchema:
    name: str
    entity_type: EntityType
    schema_file: str
    hide_from_form_panel: bool = True


BUILTIN_FORM_SCHEMAS: tuple[BuiltinFormSchema, ...] = (
    BuiltinFormSchema(
        "ETDRS-grid coordinates",
        EntityType.ImageInstance,
        "etdrs_grid_coordinates.json",
    ),
    BuiltinFormSchema(
        "Pointset registration",
        EntityType.ImageInstance,
        "pointset_registration.json",
    ),
    BuiltinFormSchema(
        "Affine registration",
        EntityType.ImageInstance,
        "affine_registration.json",
    ),
    BuiltinFormSchema(
        "RegistrationSet",
        EntityType.ImageInstance,
        "registration_set.json",
    ),
)


def schema_path(schema_file: str) -> Path:
    return _SCHEMA_DIR / schema_file
