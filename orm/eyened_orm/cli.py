import importlib
import json
from pathlib import Path
import click
from .utils.testdb import DatabaseTransfer
from .utils.config import get_config
from tqdm import tqdm

'''
Command utilities for the eyened ORM.

The following commands are available:
- test: Create a test database for ORM testing, developing new features or running alembic migrations.
- full: Create a test database for ORM testing, developing new features or running alembic migrations.
- update-thumbnails: Update thumbnails for all images in the database.
- run-models: Run the models on the database.
- zarr-tree: Display the structure of the annotations zarr store, showing groups and array shapes.

Important: import packages that are not dependencies of the ORM within the function definitions, as they are not installed by default.
'''


@click.group(name="eorm")
def eorm():
    pass


@eorm.command()
@click.option('-s', '--source', type=str, help='Source environment to use (e.g., "source")')
@click.option('-t', '--target', type=str, help='Target environment to use (e.g., "test")')
@click.option('--root-conditions', '-r', type=click.Path(exists=True), 
              help='Path to JSON file containing root conditions for database population')
def test(source, target, root_conditions):
    """Create a test database for ORM testing, with selected tables populated."""
    transfer = DatabaseTransfer(get_config(source).database, get_config(target).database)
    transfer.create_test_db(no_data=True)
    
    if root_conditions:
        with open(root_conditions, 'r') as f:
            conditions = json.load(f)
    else:
        conditions = []
    
    transfer.populate(root_conditions=conditions)


@eorm.command()
@click.option('-s', '--source', type=str, help='Source environment to use (e.g., "source")')
@click.option('-t', '--target', type=str, help='Target environment to use (e.g., "test")')
def full(source, target):
    """Create a test database for ORM testing, mirroring the source database."""
    transfer = DatabaseTransfer(get_config(source).database, get_config(target).database)
    transfer.create_test_db(no_data=False)


@eorm.command()
@click.option("-e", "--env", type=str)
@click.option("--failed", is_flag=True, default=False)
def update_thumbnails(env, failed):
    """Update thumbnails for all images in the database."""

    from eyened_orm import DBManager
    from eyened_orm.importer.thumbnails import update_thumbnails, get_missing_thumbnail_images

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

    DBManager.init(env)
    session = DBManager.get_session()

    run_inference(session, device=torch.device("cuda:0"))


@eorm.command()
@click.option("-e", "--env", type=str, help="Environment to use (e.g., 'dev', 'prod')")
@click.option("--print-errors", is_flag=True, default=False, help="Print validation errors")
def validate_forms(env, print_errors):
    """Validate form annotations and schemas in the database.

    By default, validates both schemas and form data. Use --forms-only or --schemas-only
    to validate only one aspect.
    """
    from .db import DBManager
    from .form_validation import validate_all

    DBManager.init(env)

    with DBManager.yield_session() as session:
        validate_all(session, print_errors)


@eorm.command()
@click.option("-e", "--env", type=str, help="Environment to use (e.g., 'dev', 'prod')")
def set_connection_string(env):
    config = get_config(env)
    
    password = config.database.password
    host = config.database.host
    port = config.database.port
    database = config.database.database

    package_root = Path(importlib.resources.files("eyened_orm"))   
    filename = package_root.parent / "migrations" / "alembic.ini"
    
    print(f'updating {filename} with settings from environment {env}')
    
    with open(filename, 'r') as configfile:
        lines = configfile.readlines()

    new_url = f'mysql+pymysql://root:{password}@{host}:{port}/{database}'
    for i, line in enumerate(lines):
        if line.strip().startswith('sqlalchemy.url'):
            lines[i] = f'sqlalchemy.url = {new_url}\n'
            break

    with open(filename, 'w') as configfile:
        configfile.writelines(lines)


@eorm.command()
@click.option("-e", "--env", type=str, help="Environment to use (e.g., 'dev', 'prod')")
def zarr_tree(env):
    """Display the structure of the annotations zarr store, showing groups and array shapes."""
    import zarr
    
    config = get_config(env)
    
    # Open the zarr store
    try:
        root = zarr.open_group(store=config.annotations_zarr_store, mode="r")
    except Exception as e:
        print(f"Error opening zarr store at {config.annotations_zarr_store}: {e}")
        return
    
    print(f"Zarr store: {config.annotations_zarr_store}")
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

    DBManager.init(env)

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
