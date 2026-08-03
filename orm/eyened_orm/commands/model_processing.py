from __future__ import annotations

from collections.abc import Iterable

import click

from eyened_orm import Modality
from eyened_orm.inference.etdrs_summary import run_etdrs_model

from .shared import get_database
from .targets import (
    PIPELINE_IMAGE_CHUNK_SIZE,
    filter_image_ids_by_modalities,
    image_target_options,
    iter_image_id_chunks,
    patient_target_options,
    resolve_exclude_ids,
    resolve_image_target,
    resolve_patient_target,
    target_spec_from_cli,
)


def _get_device(device: str | None):
    """Get torch device from string or auto-detect."""
    import torch
    from eyened_orm.inference.utils import auto_device

    if device is None:
        return auto_device()
    return torch.device(device)


CFI_ATTRIBUTE_MODEL_SLUGS: tuple[str, ...] = (
    "cfi-roi",
    "cfi-keypoints",
    "cfi-odfd",
    "cfi-quality",
)

CFI_SEGMENTATION_MODEL_SLUGS: tuple[str, ...] = ("cfi-amd",)

OCT_SEGMENTATION_MODEL_SLUGS: tuple[str, ...] = ("layer-segmentation",)

SEGMENTATION_MODEL_SLUGS: tuple[str, ...] = (
    *CFI_SEGMENTATION_MODEL_SLUGS,
    *OCT_SEGMENTATION_MODEL_SLUGS,
)

SEGMENTATION_SLUG_MODALITIES: dict[str, tuple[Modality, ...]] = {
    "cfi-amd": (Modality.ColorFundus,),
    "layer-segmentation": (Modality.OCT,),
}


def _cfi_pipeline_class(model_name: str):

    if model_name == "cfi-roi":
        from eyened_orm.inference.cfi_roi import CFI_ROI

        return CFI_ROI
    if model_name == "cfi-keypoints":
        from eyened_orm.inference.cfi_keypoints import CFIKeypoints

        return CFIKeypoints
    if model_name == "cfi-odfd":
        from eyened_orm.inference.cfi_odfd import CFI_ODFD

        return CFI_ODFD
    if model_name == "cfi-quality":
        from eyened_orm.inference.cfi_quality import CFI_Quality

        return CFI_Quality
    raise ValueError(f"Unknown CFI model: {model_name!r}")


def _filter_supported_modalities(
    session, image_ids: Iterable[int], modalities: tuple[Modality, ...]
) -> set[int]:
    """Keep only images whose modality is in ``modalities`` (SQL, chunked)."""
    if not modalities:
        return set(image_ids)
    return filter_image_ids_by_modalities(
        session,
        image_ids,
        modalities,
        chunk_size=PIPELINE_IMAGE_CHUNK_SIZE,
    )


def run_cfi_attribute_pipeline(
    session,
    image_ids: Iterable[int],
    model_slug: str,
    *,
    device=None,
    batch_size: int = 8,
    n_workers: int = 16,
    overwrite: bool = False,
    upgrade: bool = False,
    failed: bool = False,
    commit_interval: int = 100,
) -> None:
    """Run a single CFI attribute pipeline (one slug). RQ jobs call this once per job."""
    model_class = _cfi_pipeline_class(model_slug)
    image_ids = _filter_supported_modalities(
        session, image_ids, model_class.supported_modalities
    )
    if not image_ids:
        print(f"No images with supported modalities for {model_slug}")
        return
    print(f"Running {model_slug} ({len(image_ids)} candidate images)")
    pipeline = model_class(
        session,
        device=device,
        n_workers=n_workers,
        batch_size=batch_size,
    )

    if failed:
        scope = "failed"
    elif upgrade:
        scope = "upgrade"
    elif overwrite:
        scope = "overwrite"
    else:
        scope = "default"

    total_processed = 0
    chunks = list(iter_image_id_chunks(image_ids))
    for chunk_idx, chunk in enumerate(chunks, start=1):
        chunk_ids = chunk
        if failed:
            chunk_ids = pipeline.failed_image_ids_in_scope(chunk_ids)
            if not chunk_ids:
                continue
        filtered = pipeline.filter_image_ids(
            chunk_ids, upgrade=upgrade, failed=failed, overwrite=overwrite
        )
        if not filtered:
            continue
        print(
            f"Processing {len(filtered)} images "
            f"(chunk {chunk_idx}/{len(chunks)}, {scope})"
        )
        pipeline.run(filtered, commit_interval=commit_interval)
        session.commit()
        total_processed += len(filtered)

    if total_processed == 0:
        if failed:
            print("No failed images in scope")
        else:
            print("No images to process")
        return
    print(f"Completed processing {total_processed} images")


def _run_cfi_models_impl(
    model,
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
    commit_interval,
):
    # CFI attribute models only support ColorFundus; default the target filter
    # so "all images" does not pull every modality into Python first.
    if modality is None:
        modality = Modality.ColorFundus.name

    spec = target_spec_from_cli(
        path=path,
        image_ids=image_ids,
        project=project,
        patient=patient,
        exclude=exclude,
        modality=modality,
        include_inactive=include_inactive,
    )

    database = get_database()
    device_obj = _get_device(device)

    with database.get_session() as session:
        target = resolve_image_target(session, spec, allow_default=True)
        print(f"Target: {target.summary}")

        for slug in [model] if model is not None else CFI_ATTRIBUTE_MODEL_SLUGS:
            # cfi-roi runs first so dependent models can reuse stored CFI_ROI attributes
            run_cfi_attribute_pipeline(
                session,
                target.image_ids,
                slug,
                device=device_obj,
                batch_size=batch_size,
                n_workers=n_workers,
                overwrite=overwrite,
                upgrade=upgrade,
                failed=failed,
                commit_interval=commit_interval,
            )


@click.command(name="run-cfi-models")
@click.option(
    "-m",
    "--model",
    type=click.Choice(list(CFI_ATTRIBUTE_MODEL_SLUGS), case_sensitive=False),
    required=False,
    help="Model to run (if not specified, runs all models)",
)
@image_target_options()
@click.option(
    "-d",
    "--device",
    type=str,
    default=None,
    help="Device to use (e.g., 'cuda:0', 'cpu'). Auto-detected if not provided.",
)
@click.option(
    "-b",
    "--batch-size",
    type=int,
    default=8,
    help="Batch size for processing (not used for cfi-roi)",
)
@click.option(
    "-w",
    "--n-workers",
    type=int,
    default=16,
    help="Number of preprocessing worker processes",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing attribute values for the current model version",
)
@click.option(
    "--upgrade",
    is_flag=True,
    default=False,
    help=(
        "Run the current model version on images that lack its output, even when "
        "older versions already have AttributeValue rows (stored alongside; reads "
        "prefer the newer version). Default: skip when any version has output."
    ),
)
@click.option(
    "--failed",
    is_flag=True,
    default=False,
    help=(
        "Retry only images with a failed AttributeValue for this model (null value "
        "columns), within the selected target (project, patient, path, etc.)"
    ),
)
@click.option(
    "--commit-interval",
    type=int,
    default=100,
    help="Commit interval for processing",
)
def run_cfi_models(
    model,
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
    commit_interval,
):
    """Run CFI attribute inference models on images.

    With no targeting flags, processes all active ColorFundus images.
    Narrow scope with --path, --image-ids, --project, and/or --patient.
    Override the default modality with --modality if needed.

    Supported models:
    - cfi-roi: CFI ROI detection (no device/batch-size needed)
    - cfi-keypoints: CFI keypoints detection (fovea and disc edge)
    - cfi-odfd: Optic Disc to Fovea Distance estimation
    - cfi-quality: Image quality assessment
    """
    _run_cfi_models_impl(
        model,
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
        commit_interval,
    )


@click.command(name="run-models", hidden=True)
@click.option(
    "-m",
    "--model",
    type=click.Choice(list(CFI_ATTRIBUTE_MODEL_SLUGS), case_sensitive=False),
    required=False,
    help="Model to run (if not specified, runs all models)",
)
@image_target_options()
@click.option(
    "-d",
    "--device",
    type=str,
    default=None,
    help="Device to use (e.g., 'cuda:0', 'cpu'). Auto-detected if not provided.",
)
@click.option(
    "-b",
    "--batch-size",
    type=int,
    default=8,
    help="Batch size for processing (not used for cfi-roi)",
)
@click.option(
    "-w",
    "--n-workers",
    type=int,
    default=16,
    help="Number of preprocessing worker processes",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing attribute values for the current model version",
)
@click.option(
    "--upgrade",
    is_flag=True,
    default=False,
    help="See run-cfi-models --upgrade",
)
@click.option(
    "--failed",
    is_flag=True,
    default=False,
    help="See run-cfi-models --failed",
)
@click.option(
    "--commit-interval",
    type=int,
    default=100,
    help="Commit interval for processing",
)
def run_models(
    model,
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
    commit_interval,
):
    """Deprecated alias for run-cfi-models."""
    click.echo(
        "Warning: 'run-models' is deprecated; use 'run-cfi-models' instead.",
        err=True,
    )
    _run_cfi_models_impl(
        model,
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
        commit_interval,
    )


@click.command(name="run-segmentation")
@click.option(
    "-m",
    "--model",
    type=click.Choice(list(SEGMENTATION_MODEL_SLUGS), case_sensitive=False),
    required=False,
    help="Segmentation model to run (if not specified, runs all models)",
)
@image_target_options()
@click.option(
    "-d",
    "--device",
    type=str,
    default=None,
    help="Device to use (e.g., 'cuda:0', 'cpu'). Auto-detected if not provided.",
)
@click.option(
    "-b",
    "--batch-size",
    type=int,
    default=8,
    help="Batch size for processing",
)
@click.option(
    "-w",
    "--n-workers",
    type=int,
    default=12,
    help="Number of preprocessing worker processes",
)
@click.option(
    "--skip-existing",
    is_flag=True,
    default=True,
    help="Skip existing segmentations (filters out complete images)",
)
def run_segmentation(
    model,
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
    skip_existing,
):
    """Run segmentation inference models on a set of images.

    Supported models:
    - cfi-amd: CFI AMD segmentation (ColorFundus)
    - layer-segmentation: OCT retinal layer segmentation (nnU-Net)
    """
    spec = target_spec_from_cli(
        path=path,
        image_ids=image_ids,
        project=project,
        patient=patient,
        exclude=exclude,
        modality=modality,
        include_inactive=include_inactive,
    )

    database = get_database()
    device_obj = _get_device(device)

    with database.get_session() as session:
        target = resolve_image_target(session, spec)
        print(f"Target: {target.summary}")

        slugs = [model] if model is not None else SEGMENTATION_MODEL_SLUGS
        for slug in slugs:
            modalities = SEGMENTATION_SLUG_MODALITIES[slug]
            slug_ids = _filter_supported_modalities(
                session, target.image_ids, modalities
            )
            if not slug_ids:
                print(
                    f"No images with supported modalities for {slug} "
                    f"({', '.join(m.name for m in modalities)})"
                )
                continue
            print(
                f"Running {slug} on {len(slug_ids)} "
                f"{'/'.join(m.name for m in modalities)} images"
            )
            if slug == "cfi-amd":
                from eyened_orm.inference.cfi_amd_segmentation import run_for_image_ids

                run_for_image_ids(
                    session,
                    slug_ids,
                    device=device_obj,
                    batch_size=batch_size,
                    n_workers=n_workers,
                    overwrite=not skip_existing,
                )
            elif slug == "layer-segmentation":
                from eyened_orm.inference.layer_segmentation import run_for_image_ids

                run_for_image_ids(
                    session,
                    slug_ids,
                    device=device_obj,
                    overwrite=not skip_existing,
                )
            else:
                raise ValueError(f"Unknown segmentation model: {slug!r}")


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
    run_cfi_models,
    run_models,
    run_etdrs_model,
    run_segmentation,
    run_registration,
]
