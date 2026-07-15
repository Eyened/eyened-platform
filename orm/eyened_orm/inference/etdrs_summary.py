import click

from eyened_orm.commands.targets import image_target_options, resolve_image_target, target_spec_from_cli
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
        if not overwrite:
            existing_ids = processor.get_processed_image_ids(
                segmentation_model_id, selected_images
            )
            print(f"Skipping {len(existing_ids)} existing images")
            selected_images = selected_images - existing_ids

        empty_segmentations = ModelSegmentation.select(
            session,
            "ImageInstanceID",
            ModelID=segmentation_model_id,
            ZarrArrayIndex=None,
            ImageInstanceID=selected_images,
        )
        print(f"skipping {len(empty_segmentations)} empty segmentations")
        selected_images = selected_images - set(empty_segmentations)

        print(f"Running on {len(selected_images)} images")
        print(
            "Inputs: "
            + ", ".join(
                f"{s.attribute_name} (model {s.model_name})" for s in ETDRS_INPUTS
            )
        )

        all_segmentations = ModelSegmentation.by_columns(
            session, ModelID=segmentation_model_id, ImageInstanceID=selected_images
        )
        print(f"Found {len(all_segmentations)} segmentations")

        skipped_missing_inputs = 0
        for segmentation in tqdm(all_segmentations):
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
                print(f"Error processing instance {instance_id}: {e}")

        if skipped_missing_inputs:
            print(
                f"Skipped {skipped_missing_inputs} segmentations "
                "with missing keypoints or ODFD inputs"
            )

    print("ETDRS model processing completed successfully!")
