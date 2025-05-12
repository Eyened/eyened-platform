import tempfile

import click
from .utils.testdb import dump_database, drop_create_db, load_db, populate
from tqdm import tqdm

from .utils.config import get_config

'''
Command utilities for the eyened ORM.

The following commands are available:
- test: Create a test database for ORM testing, developing new features or running alembic migrations.
- full: Create a test database for ORM testing, developing new features or running alembic migrations.
- update-thumbnails: Update thumbnails for all images in the database.
- run-models: Run the models on the database.

Important: import packages that are not dependencies of the ORM within the function definitions, as they are not installed by default.
'''


@click.group(name="eorm")
def eorm():
    pass


@eorm.command()
def test():
    """Create a test database for ORM testing, developing new features or running alembic migrations."""
    source_db = get_config("prod").database
    test_db = get_config("dev").database

    source_db_string = (
        f"{source_db.host}:{source_db.port}/{source_db.database}"
    )
    test_db_string = f"{test_db.host}:{test_db.port}/{test_db.database}"

    print(f"Creating test database {test_db_string} from {source_db_string}..")

    # Create a temporary file to store the dump
    with tempfile.NamedTemporaryFile(mode='w+t') as dump_file:
        dump_database(source_db, dump_file, no_data=True)
        drop_create_db(test_db)
        dump_file.seek(0)
        load_db(test_db, dump_file)

        populate(source_db, test_db)

        return True


@eorm.command()
def full():
    """Create a test database for ORM testing, developing new features or running alembic migrations."""
    source_db = get_config("eyened").database
    test_db = get_config("dev").database

    source_db_string = (
        f"{source_db.host}:{source_db.port}/{source_db.database}"
    )
    test_db_string = f"{test_db.host}:{test_db.port}/{test_db.database}"

    print(f"Creating test database {test_db_string} from {source_db_string}..")

    # Create a temporary file to store the dump
    with tempfile.NamedTemporaryFile(mode='w+t') as dump_file:
        dump_database(source_db, dump_file)
        drop_create_db(test_db)
        dump_file.seek(0)
        load_db(test_db, dump_file)

        return True


@eorm.command()
@click.option("-e", "--env", type=str)
@click.option("--failed", is_flag=True, default=False)
def update_thumbnails(env, failed):
    """Update thumbnails for all images in the database."""

    from eyened_orm import DBManager
    from eyened_orm.importer.thumbnails import update_thumbnails, get_missing_thumbnail_images

    config = get_config(env)
    DBManager.init(env)
    session = DBManager.get_session()
    images = get_missing_thumbnail_images(session, failed)
    update_thumbnails(session, images)


@eorm.command()
@click.option("-e", "--env", type=str)
def run_models(env):
    import torch

    from eyened_orm import DBManager
    from eyened_orm.inference.inference import run_inference

    config = get_config(env)
    DBManager.init(config)
    session = DBManager.get_session()

    run_inference(session, config, device=torch.device("cuda:0"))


@eorm.command()
@click.option("-e", "--env", type=str, help="Environment to use (e.g., 'dev', 'prod')")
@click.option("--print-errors", is_flag=True, default=False, help="Print validation errors")
def validate_forms(env, print_errors):
    """Validate form annotations and schemas in the database.

    By default, validates both schemas and form data. Use --forms-only or --schemas-only
    to validate only one aspect.
    """
    config = get_config(env)

    from .db import DBManager
    from .form_validation import validate_all

    DBManager.init(config)

    with DBManager.yield_session() as session:
        validate_all(session, print_errors)


@eorm.command()
@click.option("-e", "--env", type=str, help="Environment to use (e.g., 'dev', 'prod')")
@click.option("--print-errors", is_flag=True, default=False, help="Print errors for failed hash calculations")
def update_hashes(env, print_errors):
    """Update FileChecksum and DataHash for all ImageInstances in the database where they are NULL.

    This command will iterate over all ImageInstances in the database with FileChecksum == None
    or DataHash == None and populate them with the outputs of im.calc_file_checksum() and 
    im.calc_data_hash() respectively.
    """
    from eyened_orm import DBManager, ImageInstance
    from sqlalchemy import or_, select

    config = get_config(env)
    DBManager.init(config)

    with DBManager.yield_session() as session:
        # Get all image instances with missing hashes
        query = select(ImageInstance).filter(
            (ImageInstance.FileChecksum == None) |
            (ImageInstance.DataHash == None)
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
                                f"Error calculating file checksum for ImageInstanceID={im.ImageInstanceID}, path={im.path}: {e}")
                        errors += 1

                if im.DataHash is None:
                    try:
                        im.DataHash = im.calc_data_hash()
                        updated = True
                    except Exception as e:
                        if print_errors:
                            print(
                                f"Error calculating data hash for ImageInstanceID={im.ImageInstanceID}, path={im.path}: {e}")
                        errors += 1

                if updated:
                    processed += 1
                    if processed % 1000 == 0:
                        session.commit()

            except Exception as e:
                if print_errors:
                    print(
                        f"Error processing ImageInstanceID={im.ImageInstanceID}: {e}")
                errors += 1

        session.commit()
        print(
            f"Completed: Updated hashes for {processed} images with {errors} errors")
