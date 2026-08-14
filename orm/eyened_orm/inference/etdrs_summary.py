from collections.abc import Iterable

import click

from eyened_orm.commands.targets import (
    PIPELINE_IMAGE_CHUNK_SIZE,
    image_target_options,
    iter_image_id_chunks,
    resolve_image_target,
    target_spec_from_cli,
)
from eyened_orm.inference.model_inputs import (
    CFI_KEYPOINTS_INPUT,
    CFI_ODFD_INPUT,
    ETDRS_INPUTS,
    resolve_input_attribute_value,
)


def resolve_etdrs_inputs(session, image_id: int) -> tuple | None:
    """Resolve keypoints and ODFD AttributeValue rows for one image.

    Uses the same version-aware :class:`ModelInputSpec` selection as CFI pipelines.
    Returns ``(keypoints_av, odfd_av)`` or ``None`` when either input is missing.
    """
    keypoints_av = resolve_input_attribute_value(
        session, image_id=image_id, spec=CFI_KEYPOINTS_INPUT
    )
    odfd_av = resolve_input_attribute_value(
        session, image_id=image_id, spec=CFI_ODFD_INPUT
    )
    if keypoints_av is None or odfd_av is None:
        return None
    return keypoints_av, odfd_av


def image_ids_with_segmentation_output(
    session,
    segmentation_model_id: int,
    image_ids: Iterable[int],
    *,
    chunk_size: int = PIPELINE_IMAGE_CHUNK_SIZE,
) -> set[int]:
    """Image IDs in ``image_ids`` that have stored ModelSegmentation output.

    A stored map means ``ZarrArrayIndex`` is set. Queries in chunks so large
    targets never build one huge ``IN (...)``.
    """
    from eyened_orm import ModelSegmentation

    ids = set(image_ids)
    if not ids:
        return set()

    found: set[int] = set()
    for chunk in iter_image_id_chunks(ids, chunk_size=chunk_size):
        rows = ModelSegmentation.select(
            session,
            "ImageInstanceID",
            ModelID=segmentation_model_id,
            ImageInstanceID=chunk,
            where=ModelSegmentation.ZarrArrayIndex.isnot(None),
        )
        found.update(rows)
    return found


@click.command(name="run-etdrs-model")
@image_target_options()
@click.option(
    "-s",
    "--segmentation-model-id",
    type=int,
    help="ID of the segmentation model",
    required=True,
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing attribute values",
)
def run_etdrs_model(
    path,
    image_ids,
    project,
    patient,
    exclude,
    modality,
    include_inactive,
    segmentation_model_id,
    overwrite,
):
    """Run ETDRS model processing on segmentations.

    Keypoints and ODFD inputs are resolved via :class:`ModelInputSpec` (highest
    available producing-model version per attribute), same as CFI attribute pipelines.
    """
    from sqlalchemy import select
    from tqdm import tqdm

    from eyened_orm import ModelSegmentation
    from eyened_orm.commands.shared import get_database
    from eyened_orm.reports.etdrs_model import ETDRSModelProcessor

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
    with database.get_session() as session:
        target = resolve_image_target(session, spec)
        selected_images = target.image_ids
        print(f"Target: {target.summary}")

        processor = ETDRSModelProcessor(session)
        with_output = image_ids_with_segmentation_output(
            session, segmentation_model_id, selected_images
        )
        print(
            f"{len(with_output)} images have ModelSegmentation output "
            f"for model {segmentation_model_id} "
            f"(of {len(selected_images)} in target)"
        )

        if not overwrite:
            existing_ids = processor.get_processed_image_ids(
                segmentation_model_id, with_output
            )
            print(f"Skipping {len(existing_ids)} existing images")
            pending = with_output - existing_ids
        else:
            pending = with_output

        print(f"Running on {len(pending)} images")
        print(
            "Inputs: "
            + ", ".join(
                f"{s.attribute_name} (model {s.model_name})" for s in ETDRS_INPUTS
            )
        )

        chunks = list(iter_image_id_chunks(pending))
        skipped_missing_inputs = 0
        total_segmentations = 0
        for chunk_idx, chunk in enumerate(chunks, start=1):
            segmentations = list(
                session.scalars(
                    select(ModelSegmentation).where(
                        ModelSegmentation.ModelID == segmentation_model_id,
                        ModelSegmentation.ImageInstanceID.in_(chunk),
                        ModelSegmentation.ZarrArrayIndex.isnot(None),
                    )
                ).all()
            )
            total_segmentations += len(segmentations)
            print(
                f"chunk {chunk_idx}/{len(chunks)}: "
                f"{len(segmentations)} segmentations"
            )
            for segmentation in tqdm(segmentations):
                instance_id = segmentation.ImageInstanceID
                try:
                    resolved = resolve_etdrs_inputs(session, instance_id)
                    if resolved is None:
                        skipped_missing_inputs += 1
                        continue
                    keypoints_av, odfd_av = resolved
                    processor.process(segmentation, keypoints_av, odfd_av)
                    session.commit()
                except Exception as e:
                    session.rollback()
                    print(f"Error processing instance {instance_id}: {e}")

        print(f"Found {total_segmentations} segmentations")
        if skipped_missing_inputs:
            print(
                f"Skipped {skipped_missing_inputs} segmentations "
                "with missing keypoints or ODFD inputs"
            )

    print("ETDRS model processing completed successfully!")
