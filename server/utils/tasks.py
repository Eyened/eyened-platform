"""RQ worker entrypoints (must stay importable and use plain, pickle-friendly args)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eyened_orm import Database

_worker_database: Database | None = None


def get_worker_database() -> Database:
    """Return one shared Database/engine per RQ worker process."""
    global _worker_database
    if _worker_database is None:
        from eyened_orm import Database

        _worker_database = Database()
    return _worker_database


def run_thumbnail_update_job(failed: bool = False, print_errors: bool = False):
    """Same as ``eorm update-thumbnails`` (optional ``--failed`` / ``--print-errors``)."""
    from eyened_orm.importer.thumbnails import run_update_thumbnails_job

    run_update_thumbnails_job(
        get_worker_database(), include_failed=failed, print_errors=print_errors
    )
    return True


def run_thumbnail_update_for_image_ids_job(
    image_ids: list[int],
    print_errors: bool = False,
):
    """Generate thumbnails only for the given ``ImageInstanceID``s."""
    from eyened_orm.importer.thumbnails import run_update_thumbnails_for_image_ids_job

    run_update_thumbnails_for_image_ids_job(
        get_worker_database(), image_ids, print_errors=print_errors
    )
    return True


def run_cfi_model_for_image_ids(
    image_ids: list[int],
    model: str,
    overwrite: bool = False,
    commit_interval: int = 100,
    batch_size: int = 8,
    n_workers: int = 16,
):
    """Run one CFI attribute pipeline (``cfi-roi``, ``cfi-quality``, ...)."""
    from eyened_orm.commands.model_processing import _get_device, run_cfi_attribute_pipeline

    database = get_worker_database()
    device = _get_device(None)
    with database.get_session() as session:
        run_cfi_attribute_pipeline(
            session,
            image_ids,
            model,
            device=device,
            batch_size=batch_size,
            n_workers=n_workers,
            overwrite=overwrite,
            commit_interval=commit_interval,
        )
    return True


def run_cfi_amd_for_image_ids(
    image_ids: list[int],
    overwrite: bool = False,
    batch_size: int = 8,
    n_workers: int = 12,
):
    """Run the CFI AMD segmentation processor (``cfi-amd`` queue)."""
    from eyened_orm.commands.model_processing import _get_device
    from eyened_orm.inference.cfi_amd_segmentation import run_for_image_ids

    database = get_worker_database()
    device = _get_device(None)
    with database.get_session() as session:
        run_for_image_ids(
            session,
            image_ids,
            device=device,
            batch_size=batch_size,
            n_workers=n_workers,
            overwrite=overwrite,
        )
    return True


# RQ default is 180s; large OCT batches need much longer (per-image wall time).
LAYER_SEGMENTATION_SECONDS_PER_IMAGE = 600
LAYER_SEGMENTATION_MIN_JOB_TIMEOUT = 600
LAYER_SEGMENTATION_MAX_JOB_TIMEOUT = 86400


def layer_segmentation_job_timeout(image_count: int) -> int:
    """RQ ``job_timeout`` for a batch of OCT layer-segmentation instances."""
    n = max(1, image_count)
    return min(
        LAYER_SEGMENTATION_MAX_JOB_TIMEOUT,
        max(
            LAYER_SEGMENTATION_MIN_JOB_TIMEOUT,
            n * LAYER_SEGMENTATION_SECONDS_PER_IMAGE,
        ),
    )


def run_layer_segmentation_for_image_ids(
    image_ids: list[int],
    overwrite: bool = False,
):
    """Run the OCT layer segmentation processor (``layer-segmentation`` queue)."""
    from rq import get_current_job

    from eyened_orm.commands.model_processing import _get_device
    from eyened_orm.inference.layer_segmentation import run_for_image_ids

    job = get_current_job()
    if job is not None:
        timeout = getattr(job, "timeout", None)
        print(
            f"[layer-segmentation] RQ job {job.id}: timeout={timeout}s, "
            f"images={len(image_ids)}",
            flush=True,
        )

    database = get_worker_database()
    device = _get_device(None)
    with database.get_session() as session:
        run_for_image_ids(session, image_ids, device=device, overwrite=overwrite)
    return True
