"""Repair ImageInstance Rows_y / Columns_x / NrOfFrames from on-disk pixels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from eyened_orm import AuditLog, ImageInstance
from eyened_orm.commands.targets import (
    TargetSpec,
    has_target_spec,
    resolve_image_target,
)
from eyened_orm.image_dimensions import (
    apply_dimensions,
    blocking_dependents,
    dimensions_compatible,
    dimensions_from_array,
    dimensions_from_instance,
)

if TYPE_CHECKING:
    from eyened_orm import Database

TRUSTED_PATH = "cli:repair-image-dimensions"


@dataclass
class RepairSummary:
    ok: int = 0
    fixed: int = 0
    blocked: int = 0
    errors: int = 0
    blocked_ids: list[int] = field(default_factory=list)
    error_ids: list[int] = field(default_factory=list)

    def print(self) -> None:
        print(
            f"Summary: ok={self.ok} fixed={self.fixed} "
            f"blocked={self.blocked} errors={self.errors}"
        )
        if self.blocked_ids:
            print(f"Blocked IDs: {self.blocked_ids}")
        if self.error_ids:
            print(f"Error IDs: {self.error_ids}")


def _project_id_for(image: ImageInstance) -> int | None:
    try:
        return image.Series.Study.Patient.ProjectID
    except Exception:
        return None


def _record_audit(session, image: ImageInstance, changes: dict) -> None:
    session.add(
        AuditLog(
            ActorID=None,
            TrustedPath=TRUSTED_PATH,
            Action="UPDATE",
            Entity="ImageInstance",
            EntityID=str(image.ImageInstanceID),
            ProjectID=_project_id_for(image),
            Changes=changes,
        )
    )


def _needs_repair(image: ImageInstance, array_dims) -> bool:
    if image.Rows_y is None or image.Columns_x is None:
        return True
    db_dims = dimensions_from_instance(image)
    return bool(dimensions_compatible(db_dims, array_dims))


def repair_image_dimensions_for_ids(
    session,
    image_ids: set[int] | list[int],
    *,
    dry_run: bool = False,
) -> RepairSummary:
    """Repair dimensions for the given ImageInstanceIDs. Caller owns commit."""
    summary = RepairSummary()
    ids = sorted(set(image_ids))
    if not ids:
        return summary

    images = (
        session.query(ImageInstance)
        .filter(ImageInstance.ImageInstanceID.in_(ids))
        .all()
    )
    by_id = {im.ImageInstanceID: im for im in images}

    for image_id in ids:
        image = by_id.get(image_id)
        if image is None:
            print(f"ImageInstance {image_id}: not found")
            summary.errors += 1
            summary.error_ids.append(image_id)
            continue
        try:
            array = image.load_pixel_array()
            array_dims = dimensions_from_array(array)
            if not _needs_repair(image, array_dims):
                summary.ok += 1
                continue

            blockers = blocking_dependents(image)
            if blockers:
                print(
                    f"ImageInstance {image_id}: blocked ({', '.join(blockers)}); "
                    f"db={dimensions_from_instance(image)} array={array_dims}"
                )
                summary.blocked += 1
                summary.blocked_ids.append(image_id)
                continue

            changes = apply_dimensions(image, array_dims)
            print(
                f"ImageInstance {image_id}: "
                f"{'would fix' if dry_run else 'fixed'} "
                f"{changes['old']} -> {changes['new']}"
            )
            if dry_run:
                image.Rows_y = changes["old"]["Rows_y"]
                image.Columns_x = changes["old"]["Columns_x"]
                image.NrOfFrames = changes["old"]["NrOfFrames"]
            else:
                _record_audit(session, image, changes)
                session.flush()
            summary.fixed += 1
        except Exception as e:
            print(f"ImageInstance {image_id}: error: {e}")
            summary.errors += 1
            summary.error_ids.append(image_id)

    return summary


def run_repair_image_dimensions(
    database: Database,
    spec: TargetSpec,
    *,
    dry_run: bool = False,
) -> RepairSummary:
    if not has_target_spec(spec):
        raise ValueError(
            "Provide at least one of --image-ids, --path, --project, or --patient"
        )

    total = RepairSummary()
    with database.get_session() as session:
        target = resolve_image_target(session, spec)
        print(f"Target: {target.summary}")
        part = repair_image_dimensions_for_ids(
            session, target.image_ids, dry_run=dry_run
        )
        total.ok += part.ok
        total.fixed += part.fixed
        total.blocked += part.blocked
        total.errors += part.errors
        total.blocked_ids.extend(part.blocked_ids)
        total.error_ids.extend(part.error_ids)
        if dry_run:
            session.rollback()
        else:
            session.commit()
    total.print()
    return total
