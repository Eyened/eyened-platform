from __future__ import annotations

from collections.abc import Callable

import click

from eyened_orm.inference.etdrs_summary import run_etdrs_model
from eyened_orm.inference.outputs import UnsupportedMode
from eyened_orm.inference.registry import MODEL_SLUGS

from .shared import get_database
from .targets import (
    image_target_options,
    patient_target_options,
    resolve_exclude_ids,
    resolve_image_target,
    resolve_patient_target,
    target_spec_from_cli,
)


def _mode(overwrite: bool, upgrade: bool, failed: bool) -> str:
    chosen = [
        name
        for name, flag in (("overwrite", overwrite), ("upgrade", upgrade), ("failed", failed))
        if flag
    ]
    if len(chosen) > 1:
        raise click.UsageError(f"Choose at most one of --{', --'.join(chosen)}")
    return chosen[0] if chosen else "default"


def run_model_options(f: Callable) -> Callable:
    for option in reversed(
        (
            click.option(
                "-m",
                "--model",
                "models",
                multiple=True,
                type=click.Choice(list(MODEL_SLUGS), case_sensitive=False),
                help="Model to run; repeatable. Default: every model, in registry order.",
            ),
            image_target_options(),
            click.option(
                "-d",
                "--device",
                default=None,
                help="Torch device (e.g. 'cuda:0', 'cpu'). Auto-detected if not provided.",
            ),
            click.option(
                "-b", "--batch-size", type=int, default=None, help="Default: per model."
            ),
            click.option(
                "-w",
                "--n-workers",
                type=int,
                default=None,
                help="Preprocessing worker processes (0 = in-process). Default: per model.",
            ),
            click.option(
                "--overwrite",
                is_flag=True,
                help="Reprocess images that already have output for the current version.",
            ),
            click.option(
                "--upgrade",
                is_flag=True,
                help=(
                    "Attribute models: run the current version on images that only have "
                    "output from older versions (stored alongside; reads prefer the newest)."
                ),
            ),
            click.option(
                "--failed",
                is_flag=True,
                help="Attribute models: retry only images whose last attempts failed.",
            ),
            click.option(
                "--upscale/--no-upscale",
                default=False,
                help=(
                    "CFI segmentations: store masks in original image space (legacy). "
                    "Default stores native model output with a projection matrix."
                ),
            ),
            click.option(
                "--commit-interval", type=int, default=None, help="Default: per output type."
            ),
        )
    ):
        f = option(f)
    return f


def _run_models(
    models,
    path,
    image_ids,
    project,
    patient,
    exclude,
    modality,
    include_inactive,
    device,
    batch_size,
    n_workers,
    overwrite,
    upgrade,
    failed,
    upscale,
    commit_interval,
) -> None:
    from eyened_orm.inference.runner import run_model

    mode = _mode(overwrite, upgrade, failed)
    spec = target_spec_from_cli(
        path=path,
        image_ids=image_ids,
        project=project,
        patient=patient,
        exclude=exclude,
        modality=modality,
        include_inactive=include_inactive,
    )
    slugs = list(models) or list(MODEL_SLUGS)
    errors: list[str] = []
    with get_database().get_session() as session:
        target = resolve_image_target(session, spec, allow_default=True)
        print(f"Target: {target.summary}")
        for slug in slugs:
            try:
                run_model(
                    session,
                    slug,
                    target.image_ids,
                    device=device,
                    mode=mode,
                    upscale=upscale,
                    batch_size=batch_size,
                    n_workers=n_workers,
                    commit_interval=commit_interval,
                )
            except UnsupportedMode as exc:
                if models:
                    raise click.UsageError(f"{slug}: {exc}") from exc
                print(f"Skipping {slug}: {exc}")
            except RuntimeError as exc:
                errors.append(str(exc))
    if errors:
        raise click.ClickException("\n".join(errors))


@click.command(name="run-model")
@run_model_options
def run_model_command(**kwargs):
    """Run registered inference models on images and store their output.

    With no targeting flags, processes all active images; each model only sees
    images of its modalities. With no -m, models run in registry order, so
    producers (cfi-roi) run before the models that consume their output.
    """
    _run_models(**kwargs)


@click.command(name="run-models", hidden=True)
@run_model_options
def run_models(**kwargs):
    """Deprecated alias for run-model."""
    click.echo("Warning: 'run-models' is deprecated; use 'run-model' instead.", err=True)
    _run_models(**kwargs)


@click.command(name="run-registration")
@patient_target_options()
@click.option(
    "--replace",
    is_flag=True,
    required=False,
    default=False,
    help="Replace existing registration",
)
def run_registration(path, image_ids, project, patient, exclude, replace):
    """Run pairwise enface registration for patients or projects.

    Stores transforms in a patient-level Registration attribute (JSON).
    Scope with --patient, --project, or --path/--image-ids. See --help for
    --replace and --skip.
    """
    from eyened_orm import AttributeDefinition, AttributesModel
    from eyened_orm.utils.registration import run_patient
    import rtnls_registration

    spec = target_spec_from_cli(
        path=path,
        image_ids=image_ids,
        project=project,
        patient=patient,
        exclude=exclude,
    )

    database = get_database()
    with database.get_session() as session:
        skip_ids = resolve_exclude_ids(session, exclude)
        if skip_ids:
            print(f"Skipping {len(skip_ids)} image(s): {skip_ids}")

        target = resolve_patient_target(session, spec)
        print(f"Target: {target.summary}")

        definition = AttributeDefinition.get_or_create(
            session,
            match_by={"AttributeName": "Registration"},
            create_kwargs={"AttributeDataType": "JSON"},
        )
        model = AttributesModel.get_or_create(
            session,
            match_by={
                "ModelName": "retinalysis-registration",
                "Version": rtnls_registration.__version__,
            },
            update_values={
                "Description": "Pairwise image registration for CFI, AF and IR"
            },
        )

        for pat in target.patients:
            run_patient(session, pat, definition, model, replace, skip_ids)


model_commands = [
    run_model_command,
    run_models,
    run_etdrs_model,
    run_registration,
]
