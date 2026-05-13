"""RQ worker entrypoints (must stay importable and use plain, pickle-friendly args)."""


def run_thumbnail_update_job(failed: bool = False, print_errors: bool = False):
    """Same as ``eorm update-thumbnails`` (optional ``--failed`` / ``--print-errors``)."""
    from eyened_orm.importer.thumbnails import run_update_thumbnails_job

    run_update_thumbnails_job(failed=failed, print_errors=print_errors)
    return True


def run_thumbnail_update_for_image_ids_job(
    image_ids: list[int],
    print_errors: bool = False,
):
    """Generate thumbnails only for the given ``ImageInstanceID``s."""
    from eyened_orm.importer.thumbnails import run_update_thumbnails_for_image_ids_job

    run_update_thumbnails_for_image_ids_job(image_ids, print_errors=print_errors)
    return True


def run_cfi_model_for_image_ids(
    image_ids: list[int],
    model: str,
    overwrite: bool = False,
    commit_interval: int = 100,
    batch_size: int = 8,
    n_workers: int = 16,
):
    """Run one CFI pipeline; ``model`` is a slug (``cfi-quality``, ...). One RQ job per model."""
    from eyened_orm import Database
    from eyened_orm.commands.model_processing import (
        _get_device,
        run_cfi_attribute_pipeline,
        run_cfi_segmentation_pipeline,
    )

    database = Database()
    device = _get_device(None)
    with database.get_session() as session:
        if model == "cfi-amd":
            run_cfi_segmentation_pipeline(
                session,
                image_ids,
                model,
                device=device,
                batch_size=batch_size,
                n_workers=n_workers,
                overwrite=overwrite,
            )
        else:
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
