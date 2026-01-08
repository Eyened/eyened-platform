from typing import Optional
import yaml
from pathlib import Path
import click
import random
import string

from .utils.testdb import DatabaseTransfer, drop_create_db, load_db, stream_mirror_database
from tqdm import tqdm
from .utils.config import (
    DatabaseSettings,
    EyenedORMConfig,
    load_config,
)

"""
Command utilities for the eyened ORM.

The following commands are available:
- test: Create a test database for ORM testing, developing new features or running alembic migrations.
- full: Create a test database for ORM testing, developing new features or running alembic migrations.
- update-thumbnails: Update thumbnails for all images in the database.
- run-models: Run the models on the database.
- zarr-tree: Display the structure of the zarr store, showing groups and array shapes.
- defragment-zarr: Defragment the zarr store by copying all segmentations to a new store with sequential indices.
- load-dump: Load a database dump file, replacing the entire database.

Important: import packages that are not dependencies of the ORM within the function definitions, as they are not installed by default.
"""


@click.group(name="eorm")
def eorm():
    pass


def transfer_db(config_file):
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    # Create DatabaseSettings directly from the nested dict
    source = DatabaseSettings(**config["source"]["database"])
    target = DatabaseSettings(**config["target"]["database"])

    print("Transferring from:")
    print(f"{source.host}:{source.port}/{source.database} ({source.user})")
    print("to:")
    print(f"{target.host}:{target.port}/{target.database} ({target.user})")

    transfer = DatabaseTransfer(source, target)
    return transfer, config


@eorm.command()
@click.option(
    "--config-file",
    "-c",
    type=click.Path(exists=True),
    help="Path to YAML file containing database configuration",
)
def database_mirror_test(config_file):
    """Create a test database for ORM testing, with selected tables populated."""
    transfer, config = transfer_db(config_file)
    transfer.create_test_db(no_data=True)
    transfer.populate(copy_objects=config["copy_objects"])

    if config["copy_segmentation_data"]:
        from eyened_orm import Database, ModelSegmentation

        # Load config from nested dicts (with secret_key override if needed)
        target_config = load_config(config["target"])
        source_config = load_config(config["source"])

        target_db = Database(target_config)
        source_db = Database(source_config)

        print("target db zarr store", target_db.config.segmentations_zarr_store)
        print("source db zarr store", source_db.config.segmentations_zarr_store)

        with target_db.get_session() as target_session:

            segs = ModelSegmentation.fetch_all(target_session)

            with source_db.get_session() as source_session:
                for seg in segs:
                    source_seg = ModelSegmentation.by_id(
                        source_session, seg.ModelSegmentationID
                    )
                    print("transfer data from", source_seg.ModelSegmentationID)
                    print("seg", seg.config.segmentations_zarr_store)
                    print(
                        "seg.storage_manager.store_path", seg.storage_manager.store_path
                    )
                    print("source_seg", source_seg.config.segmentations_zarr_store)

                    seg.ZarrArrayIndex = None
                    seg.write_data(source_seg.read_data())

                target_session.commit()


@eorm.command()
@click.option(
    "--config-file",
    "-c",
    type=click.Path(exists=True),
    help="Path to YAML file containing database configuration",
)
def database_mirror_full(config_file):
    transfer, config = transfer_db(config_file)
    transfer.create_test_db(no_data=False)


@eorm.command()
@click.option(
    "--config-file",
    "-c",
    type=click.Path(exists=True),
    help="Path to YAML file containing database configuration",
)
@click.option("--force", is_flag=True, default=False, help="Continue on SQL errors while loading")
@click.option("--no-routines", is_flag=True, default=False, help="Do not include stored routines")
@click.option("--no-triggers", is_flag=True, default=False, help="Do not include triggers")
@click.option("--no-events", is_flag=True, default=False, help="Do not include events")
def database_mirror_stream(config_file, force, no_routines, no_triggers, no_events):
    """Mirror the entire source database into the target database via a streaming pipe.

    This will DROP and recreate the target database, then stream:
      mysqldump (source) | mysql (target)
    """

    transfer, _config = transfer_db(config_file)

    print("WARNING: This will permanently delete all existing data in the target database.")
    print("\n" + "=" * 60)
    print(
        f"Target to be cleared: {transfer.test_db.database} on {transfer.test_db.host}:{transfer.test_db.port}"
    )
    print("=" * 60)

    confirmation_code = "".join(random.choices(string.ascii_uppercase, k=4))
    print(f"\nDo you want to proceed? Type '{confirmation_code}' to confirm:")
    user_input = click.prompt("", type=str)
    if user_input != confirmation_code:
        print("Confirmation code does not match. Operation cancelled.")
        return

    print("Confirmation received. Proceeding with database mirror...\n")

    print("Clearing target database...")
    if not drop_create_db(transfer.test_db):
        print("Error: Failed to clear target database")
        return

    print("\nStreaming full mirror...")
    stream_mirror_database(
        transfer.source_db,
        transfer.test_db,
        include_routines=not no_routines,
        include_triggers=not no_triggers,
        include_events=not no_events,
        force=force,
    )
    print("\nDatabase mirror completed successfully!")

@eorm.command()
@click.option(
    "-e", "--env", type=str, help="Path to .env file for environment configuration"
)
@click.option("--failed", is_flag=True, default=False)
@click.option("--print-errors", is_flag=True, default=False)
def update_thumbnails(env, failed, print_errors):
    """Update thumbnails for all images in the database."""

    from eyened_orm import Database
    from eyened_orm.importer.thumbnails import (
        update_thumbnails,
        get_missing_thumbnail_images,
    )

    config = load_config(env)
    database = Database(config)

    with database.get_session() as session:
        images = get_missing_thumbnail_images(session, failed)
        update_thumbnails(session, images, print_errors=print_errors)


@eorm.command()
@click.option(
    "-e", "--env", type=str, help="Path to .env file for environment configuration"
)
@click.option("-d", "--device", type=str, default=None)
def run_models(env, device):
    import torch
    import tempfile

    from eyened_orm import Database
    from eyened_orm.inference.inference import run_inference
    from eyened_orm.inference.utils import auto_device

    config = load_config(env)
    database = Database(config)
    with database.get_session() as session:
        if device is None:
            device = auto_device()
        else:
            device = torch.device(device)

        cfi_cache_path = config.cfi_cache_path
        if cfi_cache_path is None:
            with tempfile.TemporaryDirectory() as temp_dir:
                cfi_cache_path = Path(temp_dir)
                config.cfi_cache_path = cfi_cache_path

                print(f"Using temporary cfi_cache_path: {cfi_cache_path}")

        else:
            print(f"Running inference with cfi_cache_path: {cfi_cache_path}")
        run_inference(session, device=device, cfi_cache_path=cfi_cache_path)


@eorm.command()
@click.option(
    "-e", "--env", type=str, help="Path to .env file for environment configuration"
)
@click.option("-d", "--device", type=str, default=None)
@click.option("-b", "--batch-size", type=int, default=8)
@click.option(
    "-p", "--path", type=str, required=True, help="Path to file containing image IDs"
)
@click.option(
    "-m",
    "--model-version",
    type=str,
    required=True,
    help="Version of the model",
    default="odfd_march25",
)
@click.option(
    "-s",
    "--skip-existing",
    is_flag=True,
    default=True,
    help="Skip existing attribute values",
)
def run_odfd_model(env, device, batch_size, path, model_version, skip_existing):

    import torch
    from rtnls_inference import RegressionEnsemble
    from rtnls_inference.utils import decollate_batch
    from eyened_orm import Database, ImageInstance
    from eyened_orm.inference.utils import (
        get_or_create_attributes_model,
        get_or_create_attribute_definition,
    )
    from eyened_orm.attributes import AttributeDataType, AttributeValue
    from dotenv import load_dotenv
    from sqlalchemy import select
    import os

    load_dotenv(env)

    with open(path, "r") as f:
        image_ids = {int(line.strip()) for line in f.readlines()}

    database = Database(env)
    db_config = database.config.database
    print(f"Connected to database {db_config.database} on {db_config.host}:{db_config.port}")

    with database.get_session() as session:

        model = get_or_create_attributes_model(
            session,
            "ODFD",
            model_version,
            "Estimates the distance from the fovea to optic disc border in pixels",
        )
        attr_definition = get_or_create_attribute_definition(
            session, "ODFD", AttributeDataType.Float
        )
        model_id = model.ModelID
        attr_id = attr_definition.AttributeID

        if skip_existing:

            existing_ids = set(session.scalars(
                select(AttributeValue.ImageInstanceID).where(
                    AttributeValue.AttributeID == attr_id,
                    AttributeValue.ModelID == model_id,
                    AttributeValue.ImageInstanceID.in_(image_ids),
                )
            ).all())
            print(f"Skipping {len(existing_ids)} existing images")
            image_ids = image_ids - existing_ids

        if not image_ids:
            print("No images to run on")
            return
        else:
            print(f"Running {len(image_ids)} images")
        images = ImageInstance.by_ids(session, image_ids)
        paths = [image.path for image in images]
        ids = [image.ImageInstanceID for image in images]

    print(f"Loading model {model_version} from {os.getenv('RTNLS_MODEL_RELEASES')}")
    ensemble = RegressionEnsemble.from_release(f"{model_version}.pt").to(device)

    dataloader = ensemble._make_inference_dataloader(
        paths,
        ids=ids,
        num_workers=batch_size,
        preprocess=True,
        batch_size=batch_size,
    )
    with torch.no_grad():
        # Note: DataLoader errors can be raised during iteration (__next__) before the loop body runs.
        # To be able to catch-and-continue, we need to manually call next() on the iterator.
        it = iter(dataloader)
        try:
            total = len(dataloader)
        except TypeError:
            total = None
        pbar = tqdm(total=total)

        while True:
            try:
                batch = next(it)
            except StopIteration:
                break
            except Exception as e:
                print(e)
                pbar.update(1)
                continue

            if len(batch) == 0:
                pbar.update(1)
                continue

            im = batch["image"].to(device)
            val = (
                ensemble.forward(im).mean(dim=0).detach().cpu()
            )  # average the model dimension

            batch["val"] = val
            items = decollate_batch(batch)

            for item in items:
                scaling_factor = item["metadata"]["bounds"]["radius"] / 512
                val = item["val"] * 1024 * scaling_factor
                image_id = item["id"]
                AttributeValue.upsert(
                    session,
                    match_by={
                        "AttributeID": attr_id,
                        "ModelID": model_id,
                        "ImageInstanceID": image_id,
                    },
                    update_values={"ValueFloat": val},
                )
            session.commit()
            pbar.update(1)

        pbar.close()

@eorm.command()
@click.option(
    "-e", "--env", type=str, help="Path to .env file for environment configuration"
)
@click.option(
    "--print-errors", is_flag=True, default=False, help="Print validation errors"
)
def validate_forms(env, print_errors):
    """Validate form annotations and schemas in the database.

    By default, validates both schemas and form data. Use --forms-only or --schemas-only
    to validate only one aspect.
    """
    from eyened_orm import Database
    from .form_validation import validate_all

    config = load_config(env)
    database = Database(config)

    with database.get_session() as session:
        validate_all(session, print_errors)


@eorm.command()
@click.option(
    "-e", "--env", type=str, help="Path to .env file for environment configuration"
)
def zarr_tree(env):
    """Display the structure of the zarr store, showing groups and array shapes."""
    import zarr

    config = load_config(env)

    # Open the zarr store
    try:
        root = zarr.open_group(store=config.segmentations_zarr_store, mode="r")
    except Exception as e:
        print(f"Error opening zarr store at {config.segmentations_zarr_store}: {e}")
        return

    print(f"Zarr store: {config.segmentations_zarr_store}")
    print("=" * 50)

    # Iterate through groups
    group_names = list(root.group_keys())
    if not group_names:
        print("No groups found in the zarr store")
        return

    for group_name in sorted(group_names):
        group = root[group_name]
        print(f"\nGroup: {group_name}")
        print("-" * 30)

        # Get arrays in this group
        array_names = list(group.array_keys())
        if not array_names:
            print("  No arrays found in this group")
            continue

        for array_name in sorted(array_names):
            array = group[array_name]
            print(f"  Array: {array_name}")
            print(f"    Shape: {array.shape}")
            print(f"    Dtype: {array.dtype}")
            print(f"    Chunks: {array.chunks}")

            # # Show compression info if available
            # if hasattr(array, 'compressor') and array.compressor:
            #     print(f"    Compressor: {array.compressor}")

            # # Calculate storage efficiency
            # if hasattr(array, 'nbytes') and hasattr(array, 'nbytes_stored'):
            #     ratio = array.nbytes / array.nbytes_stored if array.nbytes_stored > 0 else 0
            #     print(f"    Storage: {array.nbytes_stored:,} bytes ({ratio:.1f}x compression)")


@eorm.command()
@click.option(
    "-e", "--env", type=str, help="Path to .env file for environment configuration"
)
@click.option(
    "--new-store-path",
    type=click.Path(),
    required=True,
    help="Path to the new zarr store directory",
)
def defragment_zarr(env, new_store_path):
    """Defragment the zarr store by copying all segmentations to a new store with sequential indices.

    This command creates a new zarr store and copies all existing segmentations to it,
    assigning new sequential ZarrArrayIndex values to eliminate gaps and improve storage efficiency.
    The ZarrArrayIndex values in the database will be updated to reflect the new indices.
    """
    from pathlib import Path

    from orm.eyened_orm.utils.zarr.manager import ZarrStorageManager

    config = load_config(env)

    # Create new store path if it doesn't exist
    new_store_path = Path(new_store_path)
    new_store_path.mkdir(parents=True, exist_ok=True)

    # Create annotation zarr storage manager for existing store
    old_manager = ZarrStorageManager(config.segmentations_zarr_store)

    print(f"Defragmenting zarr store from: {config.segmentations_zarr_store}")
    print(f"Creating new zarr store at: {new_store_path}")
    print("=" * 50)

    try:
        # Run defragmentation
        index_mapping = old_manager.defragment_to_new_store(new_store_path)

        print("\nDefragmentation completed successfully!")
        print(f"New zarr store created at: {new_store_path}")
        print("Remember to update your configuration to point to the new store.")

    except Exception as e:
        print(f"Error during defragmentation: {e}")
        import traceback

        traceback.print_exc()
        return


@eorm.command()
@click.option(
    "-e", "--env", type=str, help="Path to .env file for environment configuration"
)
@click.option(
    "--print-errors",
    is_flag=True,
    default=False,
    help="Print errors for failed hash calculations",
)
def update_hashes(env, print_errors):
    """Update FileChecksum and DataHash for all ImageInstances in the database where they are NULL.

    This command will iterate over all ImageInstances in the database with FileChecksum == None
    or DataHash == None and populate them with the outputs of im.calc_file_checksum() and
    im.calc_data_hash() respectively.
    """
    from eyened_orm import Database, ImageInstance
    from sqlalchemy import select

    config = load_config(env)
    database = Database(config)

    with database.get_session() as session:
        # Get all image instances with missing hashes
        query = select(ImageInstance).filter(
            (ImageInstance.FileChecksum == None) | (ImageInstance.DataHash == None)
        )

        images = session.execute(query).scalars().all()
        total = len(images)

        print(f"Found {total} images with missing hashes")
        processed = 0
        errors = 0

        for im in tqdm(images):
            try:
                updated = False

                if im.FileChecksum is None:
                    try:
                        im.FileChecksum = im.calc_file_checksum()
                        updated = True
                    except Exception as e:
                        if print_errors:
                            print(
                                f"Error calculating file checksum for ImageInstanceID={im.ImageInstanceID}, path={im.path}: {e}"
                            )
                        errors += 1

                if im.DataHash is None:
                    try:
                        im.DataHash = im.calc_data_hash()
                        updated = True
                    except Exception as e:
                        if print_errors:
                            print(
                                f"Error calculating data hash for ImageInstanceID={im.ImageInstanceID}, path={im.path}: {e}"
                            )
                        errors += 1

                if updated:
                    processed += 1
                    if processed % 1000 == 0:
                        session.commit()

            except Exception as e:
                if print_errors:
                    print(f"Error processing ImageInstanceID={im.ImageInstanceID}: {e}")
                errors += 1

        session.commit()
        print(f"Completed: Updated hashes for {processed} images with {errors} errors")


@eorm.command()
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
    help="Comma-separated list of ImageInstanceIDs to skip during registration (e.g. --skip 1811325,1811324,1811323)",
)
def run_registration(env, patient, project, schema, creator, replace, skip):
    from eyened_orm import Database, Patient, Project
    from eyened_orm.utils.registration import (
        get_or_create_schema,
        get_or_create_creator,
        run_patient,
    )

    # Parse skip list from comma-separated string
    skip_ids = None
    if skip:
        try:
            skip_ids = [int(id.strip()) for id in skip.split(",") if id.strip()]
            print(f"Skipping {len(skip_ids)} imageInstanceIDs: {skip_ids}")
        except ValueError as e:
            print(f"Error parsing skip list: {e}. Expected comma-separated integers.")
            return

    config = load_config(env)
    database = Database(config)
    with database.get_session() as session:

        schema = get_or_create_schema(session, schema)
        creator = get_or_create_creator(session, creator)
        if patient:
            patients = Patient.where(session, Patient.PatientIdentifier == patient)
            for patient in patients:
                run_patient(session, patient, schema, creator, replace, skip_ids)
        elif project:
            project = Project.by_id(session, project)
            patients = Patient.where(session, Patient.ProjectID == project.ProjectID)
            for patient in patients:
                run_patient(session, patient, schema, creator, replace, skip_ids)
        else:
            print("No patient or project provided")


@eorm.command()
@click.option(
    "-e", "--env", type=str, help="Path to .env file for environment configuration"
)
@click.option(
    "--dump-path",
    "-d",
    type=click.Path(exists=True),
    required=True,
    help="Path to SQL dump file to load",
)
def load_dump(env, dump_path):
    """Load a database dump file, replacing the entire database.

    This command will:
    1. Drop and recreate the database (clearing all data)
    2. Load the SQL dump file into the database

    WARNING: This will permanently delete all existing data in the database.
    """
    from pathlib import Path

    config = load_config(env)
    db_config = config.database

    dump_path = Path(dump_path)
    if not dump_path.exists():
        print(f"Error: Dump file not found: {dump_path}")
        return

    print(f"Loading database dump from: {dump_path}")
    print(f"Target database: {db_config.database} on {db_config.host}:{db_config.port}")
    print("WARNING: This will replace the entire database!")

    # Security confirmation
    print("\n" + "=" * 60)
    print(
        f"Database to be cleared: {db_config.database} on {db_config.host}:{db_config.port}"
    )
    print("=" * 60)

    # Generate random confirmation code
    confirmation_code = "".join(random.choices(string.ascii_uppercase, k=4))
    print(f"\nDo you want to proceed? Type '{confirmation_code}' to confirm:")

    user_input = click.prompt("", type=str)

    if user_input != confirmation_code:
        print("Confirmation code does not match. Operation cancelled.")
        return

    print("Confirmation received. Proceeding with database load...\n")

    # Drop and recreate the database
    print("Clearing database...")
    if not drop_create_db(db_config):
        print("Error: Failed to clear database")
        return

    # Load the dump file
    print("\nLoading dump file...")
    with open(dump_path, "r", encoding="utf-8") as dump_file:
        if not load_db(db_config, dump_file, force=True):
            print("Error: Failed to load database dump")
            return

    print("\nDatabase dump loaded successfully!")
