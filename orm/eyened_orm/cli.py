import yaml
import click
import random
import string

from .utils.testdb import drop_create_db, load_db, stream_mirror_database
from tqdm import tqdm
from .utils.config import (
    DatabaseSettings,
    load_config,
)
from .commands.model_processing import model_commands
from .commands.shared import get_database

"""
Command utilities for the eyened ORM.

The following commands are available:
- database-mirror: Mirror the entire source database into the target database via a streaming pipe.
- update-thumbnails: Update thumbnails for all images in the database.
- run-models: Run attribute inference models (cfi-roi, cfi-keypoints, cfi-odfd, cfi-quality) on a set of image IDs.
- run-etdrs-model: Run ETDRS model processing on segmentations.
- run-cfi-amd: Run CFI AMD segmentation models.
- run-registration: Run image registration for patients or projects.
- validate-forms: Validate form annotations and schemas in the database.
- zarr-tree: Display the structure of the zarr store, showing groups and array shapes.
- defragment-zarr: Defragment the zarr store by copying all segmentations to a new store with sequential indices.
- update-hashes: Update FileChecksum and DataHash for ImageInstances where they are NULL.
- load-dump: Load a database dump file, replacing the entire database.

Important: import packages that are not dependencies of the ORM within the function definitions, as they are not installed by default.
"""


@click.group(name="eorm")
def eorm():
    pass


for command in model_commands:
    eorm.add_command(command)


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

    # Return a simple namespace-like object with source_db and test_db attributes
    class TransferConfig:
        def __init__(self, source_db, test_db):
            self.source_db = source_db
            self.test_db = test_db

    return TransferConfig(source, target), config


@eorm.command()
@click.option(
    "--config-file",
    "-c",
    type=click.Path(exists=True),
    help="Path to YAML file containing database configuration",
)
@click.option(
    "--force", is_flag=True, default=False, help="Continue on SQL errors while loading"
)
@click.option(
    "--no-routines", is_flag=True, default=True, help="Do not include stored routines"
)
@click.option(
    "--no-triggers", is_flag=True, default=True, help="Do not include triggers"
)
@click.option("--no-events", is_flag=True, default=True, help="Do not include events")
def database_mirror(config_file, force, no_routines, no_triggers, no_events):
    """Mirror the entire source database into the target database via a streaming pipe.

    This will DROP and recreate the target database, then stream:
      mysqldump (source) | mysql (target)
    """

    transfer, _ = transfer_db(config_file)

    print(
        "WARNING: This will permanently delete all existing data in the target database."
    )
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

    database = get_database(env)

    with database.get_session() as session:
        images = get_missing_thumbnail_images(session, failed)
        update_thumbnails(session, images, print_errors=print_errors)


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

    from .form_validation import validate_all

    database = get_database(env)

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
    from eyened_orm import ImageInstance
    from sqlalchemy import select

    database = get_database(env)

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
