"""Study panel extensions: protocol, payload, and directory loader.

Site modules are bind-mounted into ``EXTENSIONS_DIR`` and loaded by file path.
This module must not live in that directory: a bind mount replaces it.
"""
from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from eyened_orm import Study
from eyened_orm.patient import SexEnum

EXTENSIONS_DIR = Path(__file__).parent / "extensions"


class ExtensionLoadError(Exception):
    """A drop-in module could not be loaded. Fail process startup."""


class TablesContribution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["tables"] = "tables"
    groups: dict[str, list[list[str | int | float | None]]] = Field(min_length=0)


@dataclass(frozen=True)
class ExtensionContext:
    study_id: int
    study_date: date
    study_round: int | None
    study_description: str | None
    patient_id: int
    patient_identifier: str
    patient_birth_date: date | None
    patient_sex: SexEnum | None
    project_id: int
    project_name: str
    actor_id: int
    actor_username: str
    session: Session = field(compare=False, hash=False)


@runtime_checkable
class StudyExtension(Protocol):
    name: str

    def applies(self, ctx: ExtensionContext) -> bool: ...

    def fetch(self, ctx: ExtensionContext) -> TablesContribution | None: ...


def _is_extension(obj: object) -> bool:
    return (
        not isinstance(obj, type)
        and isinstance(obj, StudyExtension)
        and isinstance(getattr(obj, "name", None), str)
        and bool(obj.name.strip())
    )


def _import_file(path: Path):
    name = f"eyened_site_extension_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ExtensionLoadError(f"Cannot import {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_extensions(path: Path | None = None) -> tuple[StudyExtension, ...]:
    directory = EXTENSIONS_DIR if path is None else path
    if not directory.exists():
        return ()
    if not directory.is_dir():
        raise ExtensionLoadError(f"{directory} is not a directory")
    loaded: list[StudyExtension] = []
    seen: dict[str, str] = {}
    for file in sorted(directory.glob("*.py")):
        if file.name.startswith("_"):
            continue
        try:
            module = _import_file(file)
        except Exception as exc:
            raise ExtensionLoadError(f"Cannot import {file.name}") from exc
        raw = getattr(module, "extensions", None)
        if raw is None or isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
            raise ExtensionLoadError(f"{file.name} must export an extensions sequence")
        for obj in raw:
            if not _is_extension(obj):
                raise ExtensionLoadError(f"{file.name} has an object that is not a StudyExtension")
            if obj.name in seen:
                raise ExtensionLoadError(
                    f"Duplicate extension name {obj.name!r} ({seen[obj.name]} and {file.name})"
                )
            seen[obj.name] = file.name
            loaded.append(obj)
    return tuple(loaded)


@lru_cache
def get_extensions() -> tuple[StudyExtension, ...]:
    return load_extensions(EXTENSIONS_DIR)


def extension_context(
    study: Study,
    *,
    actor_id: int,
    actor_username: str,
    session: Session,
) -> ExtensionContext:
    patient = study.Patient
    project = patient.Project
    return ExtensionContext(
        study_id=study.StudyID,
        study_date=study.StudyDate,
        study_round=study.StudyRound,
        study_description=study.StudyDescription,
        patient_id=patient.PatientID,
        patient_identifier=patient.PatientIdentifier,
        patient_birth_date=patient.BirthDate,
        patient_sex=patient.Sex,
        project_id=project.ProjectID,
        project_name=project.ProjectName,
        actor_id=actor_id,
        actor_username=actor_username,
        session=session,
    )
