import click
import random
import string

from .utils.testdb import drop_create_db, load_db
from tqdm import tqdm

from .commands.shared import get_database
from .utils.env import load_env_file

"""
Command utilities for the eyened ORM.

The following commands are available:
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
@click.option(
    "--env-file",
    type=click.Path(exists=True, dir_okay=False),
    required=False,
    help="Path to a .env file to load for this command",
)
def eorm(env_file):
    load_env_file(env_file, override=True)


def _register_model_commands():
    from .commands.model_processing import model_commands

    for command in model_commands:
        eorm.add_command(command)


_register_model_commands()


@eorm.command()
def create_database():
    """Create the database and tables if they don't exist."""
    from eyened_orm import create_database

    create_database()


@eorm.command()
@click.option("--username", type=str, prompt=True)
@click.option(
    "--password",
    type=str,
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
)
@click.option("--is-human", is_flag=True, default=True)
@click.option("--description", type=str, required=False)
def create_user(username: str, password: str, is_human: bool, description: str | None):
    """Create a new user with the given credentials."""

    from eyened_orm.utils.db_users import create_user

    database = get_database()
    with database.get_session() as session:
        try:
            create_user(
                session,
                username,
                password,
                is_human=is_human,
                description=description,
            )
            print(f"User created successfully")
        except ValueError as e:
            print(f"Error creating user: {e}")


@eorm.command()
@click.option("--failed", is_flag=True, default=False)
@click.option("--print-errors", is_flag=True, default=False)
def update_thumbnails(failed, print_errors):
    """Update thumbnails for all images in the database."""

    from eyened_orm import Database
    from eyened_orm.importer.thumbnails import (
        update_thumbnails,
        get_missing_thumbnail_images,
    )

    database = get_database()

    with database.get_session() as session:
        images = get_missing_thumbnail_images(session, failed)
        update_thumbnails(session, images, print_errors=print_errors)


@eorm.command()
@click.option(
    "--print-errors", is_flag=True, default=False, help="Print validation errors"
)
def validate_forms(print_errors):
    """Validate form annotations and schemas in the database.

    By default, validates both schemas and form data. Use --forms-only or --schemas-only
    to validate only one aspect.
    """

    from .form_validation import validate_all

    database = get_database()

    with database.get_session() as session:
        validate_all(session, print_errors)


@eorm.command()
def zarr_tree():
    """Display the structure of the zarr store, showing groups and array shapes."""
    import zarr

    settings = load_orm_settings()

    # Open the zarr store
    try:
        root = zarr.open_group(store=settings.segmentations_zarr_store, mode="r")
    except Exception as e:
        print(f"Error opening zarr store at {settings.segmentations_zarr_store}: {e}")
        return

    print(f"Zarr store: {settings.segmentations_zarr_store}")
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
    "--new-store-path",
    type=click.Path(),
    required=True,
    help="Path to the new zarr store directory",
)
def defragment_zarr(new_store_path):
    """Defragment the zarr store by copying all segmentations to a new store with sequential indices.

    This command creates a new zarr store and copies all existing segmentations to it,
    assigning new sequential ZarrArrayIndex values to eliminate gaps and improve storage efficiency.
    The ZarrArrayIndex values in the database will be updated to reflect the new indices.
    """
    from pathlib import Path

    from orm.eyened_orm.utils.zarr.manager import ZarrStorageManager

    settings = load_orm_settings()

    # Create new store path if it doesn't exist
    new_store_path = Path(new_store_path)
    new_store_path.mkdir(parents=True, exist_ok=True)

    # Create annotation zarr storage manager for existing store
    old_manager = ZarrStorageManager(settings.segmentations_zarr_store)

    print(f"Defragmenting zarr store from: {settings.segmentations_zarr_store}")
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
    "--print-errors",
    is_flag=True,
    default=False,
    help="Print errors for failed hash calculations",
)
def update_hashes(print_errors):
    """Update FileChecksum and DataHash for all ImageInstances in the database where they are NULL.

    This command will iterate over all ImageInstances in the database with FileChecksum == None
    or DataHash == None and populate them with the outputs of im.calc_file_checksum() and
    im.calc_data_hash() respectively.
    """
    from eyened_orm import ImageInstance
    from sqlalchemy import select

    database = get_database()

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
    "--dump-path",
    "-d",
    type=click.Path(exists=True),
    required=True,
    help="Path to SQL dump file to load",
)
def load_dump(dump_path):
    """Load a database dump file, replacing the entire database.

    This command will:
    1. Drop and recreate the database (clearing all data)
    2. Load the SQL dump file into the database

    WARNING: This will permanently delete all existing data in the database.
    """
    from pathlib import Path

    database = get_database()
    db_config = database.database_settings

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


@eorm.command()
@click.option(
    "--dump-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help="Directory to write the dated SQL dump file",
)
def save_dump(dump_dir):
    """Save a dated database dump to the given directory."""
    from datetime import datetime
    from pathlib import Path
    import subprocess

    database = get_database()
    db_config = database.database_settings

    dump_dir = Path(dump_dir)
    date_stamp = datetime.now().strftime("%Y_%m_%d")
    dump_path = dump_dir / f"eyened_db_dump_{date_stamp}.sql"

    print(f"Saving database dump to: {dump_path}")
    print(f"Source database: {db_config.database} on {db_config.host}:{db_config.port}")

    dump_cmd = [
        "mysqldump",
        "-h",
        db_config.host,
        "-P",
        str(db_config.port),
        "--single-transaction",
        "--routines",
        "-u",
        db_config.user,
        f"-p{db_config.password}",
        db_config.database,
    ]

    try:
        with open(dump_path, "w", encoding="utf-8") as dump_file:
            subprocess.run(dump_cmd, stdout=dump_file, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"Error: mysqldump failed with exit code {exc.returncode}")
        return

    print("Database dump saved successfully!")
