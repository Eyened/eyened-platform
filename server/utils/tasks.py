"""RQ worker entrypoints (must stay importable and use plain, pickle-friendly args).

Every entrypoint returns a bare bool. `GET /import/status/{task_id}` hands
`job.result` straight to its caller, so a richer return value is published, not
just recorded. Anything a caller needs beyond success/failure belongs in a
scoped route that can filter it.
"""


def run_thumbnail_update_job(failed: bool = False, print_errors: bool = False) -> bool:
    """Same as ``eorm update-thumbnails`` (optional ``--failed`` / ``--print-errors``)."""
    from eyened_orm import Database
    from eyened_orm.importer.thumbnails import run_update_thumbnails_job

    run_update_thumbnails_job(
        Database(), include_failed=failed, print_errors=print_errors
    )
    return True


def run_thumbnail_update_for_image_ids_job(
    image_ids: list[int],
    print_errors: bool = False,
) -> bool:
    """Generate thumbnails only for the given ``ImageInstanceID``s."""
    from eyened_orm import Database
    from eyened_orm.importer.thumbnails import run_update_thumbnails_for_image_ids_job

    run_update_thumbnails_for_image_ids_job(
        Database(), image_ids, print_errors=print_errors
    )
    return True


def run_model_job(
    image_ids: list[int],
    model: str,
    mode: str = "default",
    upscale: bool = False,
    batch_size: int | None = None,
    n_workers: int | None = None,
    commit_interval: int | None = None,
) -> bool:
    """Run one registered model (queue = model slug); same as ``eorm run-model -m``."""
    from eyened_orm import Database
    from eyened_orm.inference.runner import run_model

    with Database().get_session() as session:
        run_model(
            session,
            model,
            image_ids,
            mode=mode,
            upscale=upscale,
            batch_size=batch_size,
            n_workers=n_workers,
            commit_interval=commit_interval,
        )
    return True
