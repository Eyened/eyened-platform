import click

from eyened_orm.commands.targets import image_target_options, resolve_image_target, target_spec_from_cli


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
    "--keypoints-model-name",
    type=str,
    help="Name of the keypoints model",
    default="CFI_Keypoints",
)
@click.option(
    "--keypoints-model-version",
    type=str,
    help="Version of the keypoints model",
    default="july24",
)
@click.option(
    "--odfd-model-name",
    type=str,
    help="Name of the odfd model",
    default="CFI_ODFD",
)
@click.option(
    "--odfd-model-version",
    type=str,
    help="Version of the odfd model",
    default="odfd_march25",
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
    keypoints_model_name,
    keypoints_model_version,
    odfd_model_name,
    odfd_model_version,
    overwrite,
):
    """Run ETDRS model processing on segmentations."""
    from tqdm import tqdm
    from eyened_orm import AttributeValue, AttributesModel, ModelSegmentation
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

        kpts_model = AttributesModel.by_column(
            session, ModelName=keypoints_model_name, Version=keypoints_model_version
        )
        if kpts_model is None:
            raise ValueError(
                f"Keypoints model {keypoints_model_name} version {keypoints_model_version} not found"
            )

        odfd_model = AttributesModel.by_column(
            session, ModelName=odfd_model_name, Version=odfd_model_version
        )
        if odfd_model is None:
            raise ValueError(
                f"ODFD model {odfd_model_name} version {odfd_model_version} not found"
            )

        kpts = {
            av.ImageInstanceID: av
            for av in AttributeValue.by_columns(
                session,
                ModelID=kpts_model.ModelID,
                ImageInstanceID=selected_images,
            )
        }

        odfds = {
            av.ImageInstanceID: av
            for av in AttributeValue.by_columns(
                session,
                ModelID=odfd_model.ModelID,
                ImageInstanceID=selected_images,
            )
        }

        all_segmentations = ModelSegmentation.by_columns(
            session, ModelID=segmentation_model_id, ImageInstanceID=selected_images
        )
        print(f"Found {len(all_segmentations)} segmentations")

        for segmentation in tqdm(all_segmentations):
            instance_id = segmentation.ImageInstanceID
            try:
                keypoints = kpts[instance_id]
                odfd = odfds[instance_id]
                processor.process(segmentation, keypoints, odfd)
                session.commit()
            except Exception as e:
                print(f"Error processing instance {instance_id}: {e}")

    print("ETDRS model processing completed successfully!")
