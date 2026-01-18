from __future__ import annotations

from pathlib import Path

import click

from eyened_orm.inference.multi_process_inference import MultiProcessInference
from eyened_orm.inference.utils import auto_device

from .shared import get_database


def _load_image_ids(path: str) -> set[int]:
    """Load image IDs from a file (one ID per line)."""
    with open(path, "r") as f:
        return {int(line.strip()) for line in f.readlines() if line.strip()}


def _get_device(device: str | None):
    import torch

    """Get torch device from string or auto-detect."""
    if device is None:
        return auto_device()
    return torch.device(device)


@click.command(name="run-models")
@click.option(
    "-e",
    "--env",
    type=str,
    help="Path to .env file for environment configuration",
)
@click.option(
    "-m",
    "--model",
    type=click.Choice(
        ["cfi-roi", "cfi-keypoints", "cfi-odfd", "cfi-quality"], case_sensitive=False
    ),
    required=False,
    help="Model to run (if not specified, runs all models)",
)
@click.option(
    "-p",
    "--path",
    type=str,
    required=True,
    help="Path to file containing image IDs (one per line)",
)
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
    default=8,
    help="Number of preprocessing worker processes",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing attribute values (skips filtering)",
)
def run_models(env, model, path, device, batch_size, n_workers, overwrite):
    """Run attribute inference models on a set of image IDs.

    Supported models:
    - cfi-roi: CFI ROI detection (no device/batch-size needed)
    - cfi-keypoints: CFI keypoints detection (fovea and disc edge)
    - cfi-odfd: Optic Disc to Fovea Distance estimation
    - cfi-quality: Image quality assessment
    """
    database = get_database(env)

    # Load image IDs
    image_ids = _load_image_ids(path)
    print(f"Loaded {len(image_ids)} image IDs from {path}")

    device_obj = _get_device(device)

    from eyened_orm.inference.cfi_roi import CFI_ROI
    from eyened_orm.inference.cfi_keypoints import CFIKeypoints
    from eyened_orm.inference.cfi_odfd import CFI_ODFD
    from eyened_orm.inference.cfi_quality import CFI_Quality

    models = {
        "cfi-roi": CFI_ROI,
        "cfi-keypoints": CFIKeypoints,
        "cfi-odfd": CFI_ODFD,
        "cfi-quality": CFI_Quality,
    }

    with database.get_session() as session:
        for model_name, model_class in models.items():
            if model == model_name or model is None:
                print(f"Running {model_name}")
                pipeline = model_class(
                    session,
                    device=device_obj,
                    n_workers=n_workers,
                    batch_size=batch_size,
                )

                # Filter existing results unless overwrite is enabled
                if not overwrite:
                    image_ids = pipeline.filter_image_ids(image_ids)
                    print(
                        f"Processing {len(image_ids)} images (after filtering existing)"
                    )

                if not image_ids:
                    print("No images to process")
                    continue

                # Run inference
                pipeline.run(image_ids)
                session.commit()
                print(f"Completed processing {len(image_ids)} images")


# @click.command(name="run-models")
# @click.option(
#     "-e", "--env", type=str, help="Path to .env file for environment configuration"
# )
# @click.option("-d", "--device", type=str, default=None)
# def run_models(env, device):
#     """Legacy command for running basic inference models."""
#     import tempfile

#     from eyened_orm.inference.inference import run_inference

#     database = get_database(env)

#     config = load_config(env)
#     with database.get_session() as session:
#         if device is None:
#             device = auto_device()
#         else:
#             device = torch.device(device)

#         cfi_cache_path = config.cfi_cache_path
#         if cfi_cache_path is None:
#             with tempfile.TemporaryDirectory() as temp_dir:
#                 cfi_cache_path = Path(temp_dir)
#                 config.cfi_cache_path = cfi_cache_path

#                 print(f"Using temporary cfi_cache_path: {cfi_cache_path}")

#         else:
#             print(f"Running inference with cfi_cache_path: {cfi_cache_path}")
#         run_inference(session, device=device, cfi_cache_path=cfi_cache_path)


@click.command(name="run-etdrs-model")
@click.option(
    "-e", "--env", type=str, help="Path to .env file for environment configuration"
)
@click.option(
    "-p", "--path", type=str, required=True, help="Path to file containing image IDs"
)
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
    default="cf_keypoints_legacy",
)
@click.option(
    "--keypoints-model-version",
    type=str,
    help="Version of the keypoints model",
    default="1.0",
)
@click.option(
    "--odfd-model-name",
    type=str,
    help="Name of the odfd model",
    default="ODFD",
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
    env,
    path,
    segmentation_model_id,
    keypoints_model_name,
    keypoints_model_version,
    odfd_model_name,
    odfd_model_version,
    overwrite,
):
    """Run ETDRS model processing on segmentations."""
    from eyened_orm import AttributeValue, AttributesModel, ModelSegmentation
    from eyened_orm.reports.etdrs_model import ETDRSModelProcessor
    from tqdm import tqdm

    with open(path, "r") as f:
        selected_images = {int(line.strip()) for line in f.readlines()}

    database = get_database(env)
    session = database.create_session()

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

    session.close()
    print("ETDRS model processing completed successfully!")


@click.command(name="run-cfi-amd")
@click.option(
    "-e", "--env", type=str, help="Path to .env file for environment configuration"
)
@click.option(
    "-p", "--path", type=str, required=True, help="Path to file containing image IDs"
)
@click.option(
    "-d", "--device", type=str, default=None, help="Device to use for processing"
)
@click.option(
    "--skip-existing",
    is_flag=True,
    default=True,
    help="Skip existing attribute values",
)
@click.option(
    "--max-workers",
    type=int,
    default=12,
    help="Maximum number of workers to use for processing",
)
@click.option(
    "--batch-size",
    type=int,
    default=8,
    help="Batch size for processing",
)
def run_cfi_amd(env, path, device, skip_existing, max_workers, batch_size):
    """Run CFI AMD segmentation models."""
    import numpy as np
    import torch

    from eyened_orm import (
        Feature,
        SegmentationModel,
        ModelSegmentation,
        DataRepresentation,
        Datatype,
        ImageInstance,
    )

    if device is None:
        device = auto_device()
    else:
        device = torch.device(device)

    with open(path, "r") as f:
        selected_images = {int(line.strip()) for line in f.readlines()}

    print(f"Preparing to process {len(selected_images)} images")

    database = get_database(env)
    session = database.create_session()

    feature_names = {
        "drusen": ("Drusen", "Drusen"),
        "RPD": ("Reticular pseudodrusen", "Reticular pseudodrusen"),
        "hyperpigmentation": ("RPE hyperpigmentation", "Hyperpigmentation"),
        "rpe_degeneration": (
            "Retinal pigment epithelium (RPE) degeneration",
            "RPE degeneration",
        ),
    }

    features = {
        name: Feature.get_or_create(session, match_by={"FeatureName": feature_name})
        for name, (feature_name, _) in feature_names.items()
    }

    models = {
        name: SegmentationModel.get_or_create(
            session,
            match_by={
                "FeatureID": features[name].FeatureID,
                "ModelName": model_name,
                "Version": "3",
            },
            create_kwargs={"Description": "https://github.com/Eyened/cfi-amd"},
        )
        for name, (_, model_name) in feature_names.items()
    }

    model_id_by_feature = {name: model.ModelID for name, model in models.items()}
    model_ids = set(model_id_by_feature.values())

    processed = set(
        ModelSegmentation.select(
            session,
            "ModelID",
            "ImageInstanceID",
            ImageInstanceID=selected_images,
            ModelID=model_ids,
        )
    )

    complete = {
        i for i in selected_images if all((x, i) in processed for x in model_ids)
    }
    print(f"Found {len(complete)} complete images")

    if skip_existing:
        images = selected_images - complete
    else:
        images = selected_images

    print(f"Running on {len(images)} images")

    def get_model_segmentation(instance_id: int, model_id: int, h: int, w: int):
        return ModelSegmentation.get_or_create(
            session,
            match_by={
                "ImageInstanceID": instance_id,
                "ModelID": model_id,
            },
            create_kwargs={
                "ImageInstanceID": instance_id,
                "ModelID": model_id,
                "Depth": 1,
                "Width": w,
                "Height": h,
                "SparseAxis": 0,
                "DataType": Datatype.R8,
                "DataRepresentation": DataRepresentation.Probability,
                "Threshold": 0.5,
            },
        )

    def save_results(instance_id, result):
        # Get dimensions from model output (avoids depending on any ORM-loaded image data)
        any_key = next(k for k in result.keys() if k != "bounds")
        h, w = result[any_key].shape

        for feature_name, model_id in model_id_by_feature.items():
            m = get_model_segmentation(instance_id, model_id, h=h, w=w)
            try:
                arr = result[feature_name]
                if np.any(arr >= 0.5):
                    # convert float (0-1) to uint8 (0-255) for Datatype.R8
                    data = (255 * arr).astype(np.uint8)
                    m.write_data(data, axis=0)
            finally:
                # Prevent the session identity map from growing without bound.
                session.flush()
                session.expunge(m)

        session.commit()

    from cfi_amd.processor import Processor

    processor = Processor(device)

    instances = ImageInstance.by_ids(session, images)
    items = [(iid, i.path) for iid, i in instances.items()]

    mpi = MultiProcessInference(
        items, processor, n_workers=max_workers, batch_size=batch_size
    )
    for iid, result in mpi.run():
        save_results(iid, result)


@click.command(name="run-registration")
@click.option(
    "-e", "--env", type=str, help="Path to .env file for environment configuration"
)
@click.option(
    "--patient",
    type=str,
    required=False,
    help="Patient identifier to run registration for",
)
@click.option(
    "--project", type=int, required=False, help="Project ID to run registration for"
)
@click.option(
    "--schema",
    type=str,
    required=False,
    default="RegistrationSet",
    help="SchemaName to run registration for",
)
@click.option(
    "--creator",
    type=str,
    required=False,
    default="registration model",
    help="CreatorName to run registration for",
)
@click.option(
    "--replace",
    is_flag=True,
    required=False,
    default=False,
    help="Replace existing registration",
)
@click.option(
    "--skip",
    type=str,
    required=False,
    help=(
        "Comma-separated list of ImageInstanceIDs to skip during registration "
        "(e.g. --skip 1811325,1811324,1811323)"
    ),
)
def run_registration(env, patient, project, schema, creator, replace, skip):
    """Run registration processing for patients."""
    from eyened_orm import Patient, FormSchema, Creator
    from eyened_orm.utils.registration import run_patient
    import json

    # Parse skip list from comma-separated string
    skip_ids = None
    if skip:
        try:
            skip_ids = [int(id.strip()) for id in skip.split(",") if id.strip()]
            print(f"Skipping {len(skip_ids)} imageInstanceIDs: {skip_ids}")
        except ValueError as e:
            print(f"Error parsing skip list: {e}. Expected comma-separated integers.")
            return

    database = get_database(env)
    with database.get_session() as session:

        # Get or create schema - load JSON file if creating
        schema_name = schema
        schema_path = (
            Path(__file__).resolve().parents[1] / "utils" / "registration_schema.json"
        )
        with open(schema_path, "r") as f:
            schema_dict = json.load(f)
        schema = FormSchema.get_or_create(
            session,
            match_by={"SchemaName": schema_name},
            create_kwargs={"SchemaName": schema_name, "Schema": schema_dict},
            verbose=True,
        )

        # Get or create creator
        creator_name = creator
        creator = Creator.get_or_create(
            session,
            match_by={"CreatorName": creator_name},
            create_kwargs={"CreatorName": creator_name, "IsHuman": True},
            verbose=True,
        )
        if patient:
            patients = Patient.by_column(session, PatientIdentifier=patient)
        elif project:
            patients = Patient.by_column(session, ProjectID=project)
        else:
            raise ValueError("No patient or project provided")
        for patient in patients:
            run_patient(session, patient, schema, creator, replace, skip_ids)


model_commands = [
    run_models,
    run_etdrs_model,
    run_cfi_amd,
    run_registration,
]
