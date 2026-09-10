"""Shared target selection for eorm commands and future API convergence.

CLI flags map to :class:`TargetSpec`; resolvers produce canonical ``ImageInstanceID``
sets or patient lists for job runners.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from eyened_orm import Patient, Project


@dataclass
class TargetSpec:
    """Facade-agnostic scope input. CLI maps flags here; API can map JSON later."""

    image_ids: list[str] | None = None
    image_ids_file: str | None = None
    project: str | None = None
    patient: str | None = None
    exclude: list[str] | None = None
    modality: str | None = None
    include_inactive: bool = False


def has_target_spec(spec: TargetSpec) -> bool:
    return bool(
        spec.image_ids_file or spec.image_ids or spec.project or spec.patient
    )


@dataclass(frozen=True)
class ImageTarget:
    image_ids: set[int]
    summary: str


@dataclass(frozen=True)
class PatientTarget:
    patients: list[Patient]
    summary: str


# Bound large ID-set SQL filters and pipeline runs.
PIPELINE_IMAGE_CHUNK_SIZE = 10_000


def iter_image_id_chunks(
    image_ids: Iterable[int],
    *,
    chunk_size: int = PIPELINE_IMAGE_CHUNK_SIZE,
) -> Iterable[set[int]]:
    """Yield stable sorted chunks of image IDs."""
    ordered = sorted(set(image_ids))
    for start in range(0, len(ordered), chunk_size):
        yield set(ordered[start : start + chunk_size])


def _parse_comma_tokens(value: str | None) -> list[str]:
    if not value:
        return []
    return [token.strip() for token in value.split(",") if token.strip()]


def target_spec_from_cli(
    *,
    path: str | None = None,
    image_ids: str | None = None,
    project: str | None = None,
    patient: str | None = None,
    exclude: str | None = None,
    modality: str | None = None,
    include_inactive: bool = False,
) -> TargetSpec:
    project_str = str(project) if project is not None else None
    return TargetSpec(
        image_ids=_parse_comma_tokens(image_ids) or None,
        image_ids_file=path,
        project=project_str,
        patient=patient,
        exclude=_parse_comma_tokens(exclude) or None,
        modality=modality,
        include_inactive=include_inactive,
    )


def resolve_identifier(session: Session, token: str) -> int:
    """Resolve an ImageInstanceID (int string) or PublicID to internal ID."""
    from eyened_orm import ImageInstance

    token = token.strip()
    if not token or token.startswith("#"):
        raise click.UsageError("Empty image identifier")
    if token.isdigit():
        return int(token)
    image = ImageInstance.by_column(session, PublicID=token)
    if image is None:
        raise click.UsageError(f"Unknown image identifier: {token!r}")
    return image.ImageInstanceID


def resolve_project(session: Session, project: str) -> Project:
    """Resolve project by numeric ID or unique project name."""
    from eyened_orm import Project

    project = project.strip()
    if project.isdigit():
        proj = session.get(Project, int(project))
        if proj is None:
            raise click.UsageError(f"Unknown project ID: {project}")
        return proj
    proj = Project.by_name(session, project)
    if proj is None:
        raise click.UsageError(f"Unknown project name: {project!r}")
    return proj


def load_ids_from_file(session: Session, path: str) -> set[int]:
    """Load image identifiers from a file (one per line; # comments ignored)."""
    ids: set[int] = set()
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            ids.add(resolve_identifier(session, line))
    return ids


def _parse_modality(modality: str):
    from eyened_orm import Modality

    try:
        return Modality[modality]
    except KeyError as exc:
        valid = ", ".join(m.name for m in Modality)
        raise click.UsageError(
            f"Unknown modality {modality!r}; expected one of: {valid}"
        ) from exc


def _modality_where(modality: str | None):
    if modality is None:
        return None
    from eyened_orm import ImageInstance

    return ImageInstance.Modality == _parse_modality(modality)


def filter_image_ids_by_modalities(
    session: Session,
    image_ids: Iterable[int],
    modalities,
    *,
    chunk_size: int = PIPELINE_IMAGE_CHUNK_SIZE,
) -> set[int]:
    """Keep IDs whose ``ImageInstance.Modality`` is in ``modalities`` (SQL-only).

    Queries in chunks so large ID sets never build a single huge ``IN (...)``.
    """
    from eyened_orm import ImageInstance, Modality
    from sqlalchemy import select

    ids = set(image_ids)
    if not ids:
        return ids
    if modalities is None:
        return ids
    modality_list = list(modalities)
    if not modality_list:
        return ids
    normalized: list[Modality] = []
    for mod in modality_list:
        if isinstance(mod, Modality):
            normalized.append(mod)
        elif isinstance(mod, str):
            normalized.append(_parse_modality(mod))
        else:
            normalized.append(Modality(mod))

    kept: set[int] = set()
    ordered = sorted(ids)
    for start in range(0, len(ordered), chunk_size):
        chunk = ordered[start : start + chunk_size]
        stmt = select(ImageInstance.ImageInstanceID).where(
            ImageInstance.ImageInstanceID.in_(chunk),
            ImageInstance.Modality.in_(normalized),
        )
        kept.update(session.scalars(stmt).all())
    return kept


def _validate_image_spec(spec: TargetSpec, *, allow_default: bool = False) -> None:
    explicit = bool(spec.image_ids_file or spec.image_ids)
    scoped = bool(spec.project or spec.patient)
    if not explicit and not scoped and not allow_default:
        raise click.UsageError(
            "Provide a target via --path, --image-ids, --project, and/or --patient"
        )
    if explicit and spec.project and not spec.patient:
        raise click.UsageError(
            "--path/--image-ids and --project are mutually exclusive "
            "(use --patient with --project to scope a patient)"
        )


def _validate_patient_spec(spec: TargetSpec) -> None:
    explicit = bool(spec.image_ids_file or spec.image_ids)
    scoped = bool(spec.project or spec.patient)
    if not explicit and not scoped:
        raise click.UsageError(
            "Provide a target via --path, --image-ids, --project, and/or --patient"
        )


def _resolve_all_image_ids(
    session: Session,
    *,
    modality: str | None = None,
    include_inactive: bool = False,
) -> set[int]:
    """All image instance IDs, optionally filtered by modality and active status."""
    from eyened_orm import ImageInstance
    from sqlalchemy import select

    statement = select(ImageInstance.ImageInstanceID)
    if not include_inactive:
        statement = statement.where(~ImageInstance.Inactive)
    modality_where = _modality_where(modality)
    if modality_where is not None:
        statement = statement.where(modality_where)
    return set(session.scalars(statement).all())


def resolve_image_target(
    session: Session, spec: TargetSpec, *, allow_default: bool = False
) -> ImageTarget:
    """Resolve a :class:`TargetSpec` to a set of ``ImageInstanceID`` values.

    When ``spec.modality`` is set it is applied in SQL for project / patient /
    default-all paths. Explicit ``--image-ids`` / ``--path`` lists are narrowed
    afterward with :func:`filter_image_ids_by_modalities`.
    """
    _validate_image_spec(spec, allow_default=allow_default)
    where = _modality_where(spec.modality)
    image_ids: set[int] = set()
    summary_parts: list[str] = []
    from_explicit = False

    if spec.image_ids_file:
        from_file = load_ids_from_file(session, spec.image_ids_file)
        image_ids |= from_file
        summary_parts.append(f"{len(from_file)} from {spec.image_ids_file}")
        from_explicit = True

    if spec.image_ids:
        from_inline = {
            resolve_identifier(session, token) for token in spec.image_ids
        }
        image_ids |= from_inline
        summary_parts.append(f"{len(from_inline)} from --image-ids")
        from_explicit = True

    if not image_ids:
        if spec.patient:
            patients = _resolve_patients_for_spec(session, spec)
            for pat in patients:
                images = pat.get_images(
                    where=where, include_inactive=spec.include_inactive
                )
                image_ids |= {im.ImageInstanceID for im in images}
            summary_parts.append(
                f"{len(image_ids)} images for patient {spec.patient!r}"
                + (f" in project {spec.project!r}" if spec.project else "")
            )
        elif spec.project:
            proj = resolve_project(session, spec.project)
            images = proj.get_images(
                where=where, include_inactive=spec.include_inactive
            )
            image_ids = {im.ImageInstanceID for im in images}
            mod_note = f" ({spec.modality})" if spec.modality else ""
            summary_parts.append(
                f"{len(image_ids)} images in project {proj.ProjectName!r}{mod_note}"
            )
        elif allow_default:
            image_ids = _resolve_all_image_ids(
                session,
                modality=spec.modality,
                include_inactive=spec.include_inactive,
            )
            mod_note = f" ({spec.modality})" if spec.modality else ""
            summary_parts.append(f"all {len(image_ids)} images{mod_note}")

    if from_explicit and spec.modality and image_ids:
        before = len(image_ids)
        image_ids = filter_image_ids_by_modalities(
            session, image_ids, (_parse_modality(spec.modality),)
        )
        summary_parts.append(
            f"modality {spec.modality}: kept {len(image_ids)}/{before}"
        )

    if spec.exclude:
        exclude_ids = {resolve_identifier(session, token) for token in spec.exclude}
        before = len(image_ids)
        image_ids -= exclude_ids
        summary_parts.append(f"excluded {before - len(image_ids)}")

    if not image_ids:
        raise click.UsageError("Target resolved to zero images")

    summary = "; ".join(summary_parts) if summary_parts else f"{len(image_ids)} images"
    return ImageTarget(image_ids=image_ids, summary=summary)


def _resolve_patients_for_spec(session: Session, spec: TargetSpec) -> list[Patient]:
    from eyened_orm import Patient

    if not spec.patient:
        raise click.UsageError("Patient identifier required")
    if spec.project:
        proj = resolve_project(session, spec.project)
        pat = Patient.by_project_and_identifier(session, proj.ProjectID, spec.patient)
        if pat is None:
            raise click.UsageError(
                f"Patient {spec.patient!r} not found in project {proj.ProjectName!r}"
            )
        return [pat]
    patients = Patient.by_identifier(session, spec.patient)
    if not patients:
        raise click.UsageError(f"Patient {spec.patient!r} not found")
    if len(patients) > 1:
        projects = ", ".join(sorted({p.Project.ProjectName for p in patients}))
        raise click.UsageError(
            f"Patient {spec.patient!r} exists in multiple projects ({projects}); "
            "use --project to disambiguate"
        )
    return patients


def resolve_patient_target(session: Session, spec: TargetSpec) -> PatientTarget:
    """Resolve a :class:`TargetSpec` to one or more patients."""
    from eyened_orm import Patient

    _validate_patient_spec(spec)
    summary_parts: list[str] = []

    if spec.patient or spec.project:
        if spec.patient:
            patients = _resolve_patients_for_spec(session, spec)
            summary_parts.append(
                f"patient {spec.patient!r}"
                + (f" in project {spec.project!r}" if spec.project else "")
            )
        else:
            proj = resolve_project(session, spec.project)
            patients = Patient.by_columns(session, ProjectID=proj.ProjectID)
            summary_parts.append(f"all patients in project {proj.ProjectName!r}")
    else:
        image_target = resolve_image_target(session, spec)
        patient_ids = set(
            session.scalars(_patient_ids_for_images(image_target.image_ids))
        )
        if not patient_ids:
            raise click.UsageError("No patients found for the given image IDs")
        patients = Patient.by_columns(session, PatientID=patient_ids)
        summary_parts.append(
            f"{len(patients)} patients from {len(image_target.image_ids)} images"
        )

    if not patients:
        raise click.UsageError("Target resolved to zero patients")

    summary = "; ".join(summary_parts)
    return PatientTarget(patients=patients, summary=summary)


def _patient_ids_for_images(image_ids: set[int]):
    from eyened_orm import ImageInstance, Patient, Series, Study
    from sqlalchemy import select

    return (
        select(Patient.PatientID)
        .distinct()
        .select_from(ImageInstance)
        .join(Series)
        .join(Study)
        .join(Patient)
        .where(ImageInstance.ImageInstanceID.in_(image_ids))
    )


def resolve_exclude_ids(session: Session, exclude: str | None) -> list[int] | None:
    """Parse --skip/--exclude comma-separated ImageInstanceID or PublicID tokens."""
    tokens = _parse_comma_tokens(exclude)
    if not tokens:
        return None
    return [resolve_identifier(session, token) for token in tokens]


def _modality_click_type():
    from eyened_orm import Modality

    return click.Choice([m.name for m in Modality], case_sensitive=False)


def image_target_options(*, require_one: bool = True) -> Callable:
    """Click decorator: standard image targeting flags shared across eorm commands."""

    def decorator(f: Callable) -> Callable:
        f = click.option(
            "--image-ids",
            type=str,
            default=None,
            help="Comma-separated ImageInstanceIDs or PublicIDs (for small lists)",
        )(f)
        f = click.option(
            "-p",
            "--path",
            "--image-ids-file",
            "path",
            type=click.Path(exists=True, dir_okay=False),
            default=None,
            help="File with one ImageInstanceID or PublicID per line (# comments ok)",
        )(f)
        f = click.option(
            "--project",
            type=str,
            default=None,
            help="Project ID or name",
        )(f)
        f = click.option(
            "--patient",
            type=str,
            default=None,
            help="Patient identifier (use with --project when ambiguous)",
        )(f)
        f = click.option(
            "--exclude",
            "--skip",
            "exclude",
            type=str,
            default=None,
            help="Comma-separated ImageInstanceIDs or PublicIDs to exclude",
        )(f)
        f = click.option(
            "--modality",
            type=_modality_click_type(),
            default=None,
            help=(
                "Filter by modality (applied in SQL). "
                "run-cfi-models defaults to ColorFundus when omitted."
            ),
        )(f)
        f = click.option(
            "--include-inactive",
            is_flag=True,
            default=False,
            help="Include inactive image instances",
        )(f)
        return f

    return decorator


def patient_target_options(*, require_one: bool = True) -> Callable:
    """Click decorator: standard patient targeting flags for registration-style commands."""

    def decorator(f: Callable) -> Callable:
        f = click.option(
            "--image-ids",
            type=str,
            default=None,
            help="Comma-separated ImageInstanceIDs or PublicIDs; derive patients from these images",
        )(f)
        f = click.option(
            "-p",
            "--path",
            "--image-ids-file",
            "path",
            type=click.Path(exists=True, dir_okay=False),
            default=None,
            help="File with ImageInstanceIDs or PublicIDs; derive patients from these images",
        )(f)
        f = click.option(
            "--project",
            type=str,
            default=None,
            help="Project ID or name",
        )(f)
        f = click.option(
            "--patient",
            type=str,
            default=None,
            help="Patient identifier (use with --project when ambiguous)",
        )(f)
        f = click.option(
            "--skip",
            "--exclude",
            "exclude",
            type=str,
            default=None,
            help="Comma-separated ImageInstanceIDs or PublicIDs to skip",
        )(f)
        return f

    return decorator
