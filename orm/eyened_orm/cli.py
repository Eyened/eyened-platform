from typing import Optional
from dotenv import load_dotenv
import yaml
from pathlib import Path
import click
from .inference.utils import auto_device
from .utils.testdb import DatabaseTransfer
from tqdm import tqdm
from .utils.config import DatabaseSettings, EyenedORMConfig

'''
Command utilities for the eyened ORM.

The following commands are available:
- test: Create a test database for ORM testing, developing new features or running alembic migrations.
- full: Create a test database for ORM testing, developing new features or running alembic migrations.
- update-thumbnails: Update thumbnails for all images in the database.
- run-models: Run the models on the database.
- zarr-tree: Display the structure of the zarr store, showing groups and array shapes.
- defragment-zarr: Defragment the zarr store by copying all segmentations to a new store with sequential indices.

Important: import packages that are not dependencies of the ORM within the function definitions, as they are not installed by default.
'''

def load_orm_config(env: Optional[str] = None) -> EyenedORMConfig:
    if env is not None:
        load_dotenv(env)

    return EyenedORMConfig()

@click.group(name="eorm")
def eorm():
    pass


def transfer_db(config_file):

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    source = DatabaseSettings.from_dict(config['source'])
    target = DatabaseSettings.from_dict(config['target'])
    
    print('Transferring from:')
    print(f'{source.host}:{source.port}/{source.database} ({source.user})')
    print('to:')
    print(f'{target.host}:{target.port}/{target.database} ({target.user})')

    transfer = DatabaseTransfer(source, target)
    return transfer, config
    
@eorm.command()
@click.option('--config-file', '-c', type=click.Path(exists=True), help='Path to YAML file containing database configuration')
def database_mirror_test(config_file):
    """Create a test database for ORM testing, with selected tables populated."""
    transfer, config = transfer_db(config_file)
    transfer.create_test_db(no_data=True)
    transfer.populate(copy_objects=config['copy_objects'])

@eorm.command()
@click.option('--config-file', '-c', type=click.Path(exists=True), help='Path to YAML file containing database configuration')
def database_mirror_full(config_file):
    transfer, config = transfer_db(config_file)
    transfer.create_test_db(no_data=False)
    

@eorm.command()
@click.option("-e", "--env", type=str, help="Path to .env file for environment configuration")
@click.option("--failed", is_flag=True, default=False)
def update_thumbnails(env, failed):
    """Update thumbnails for all images in the database."""

    from eyened_orm import Database
    from eyened_orm.importer.thumbnails import update_thumbnails, get_missing_thumbnail_images

    config = load_orm_config(env)
    database = Database(config)
    
    with database.get_session() as session:
        images = get_missing_thumbnail_images(session, failed)
        update_thumbnails(session, images)


@eorm.command()
@click.option("-e", "--env", type=str, help="Path to .env file for environment configuration")
@click.option("-d", "--device", type=str, default=None)
def run_models(env, device):
    import torch
    import tempfile

    from eyened_orm import Database
    from eyened_orm.inference.inference import run_inference

    config = load_orm_config(env)
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

                print(f'Using temporary cfi_cache_path: {cfi_cache_path}')

        else:
            print(f'Running inference with cfi_cache_path: {cfi_cache_path}')
        run_inference(session, device=device, cfi_cache_path=cfi_cache_path)
    


@eorm.command()
@click.option("-e", "--env", type=str, help="Path to .env file for environment configuration")
@click.option("--print-errors", is_flag=True, default=False, help="Print validation errors")
def validate_forms(env, print_errors):
    """Validate form annotations and schemas in the database.

    By default, validates both schemas and form data. Use --forms-only or --schemas-only
    to validate only one aspect.
    """
    from eyened_orm import Database
    from .form_validation import validate_all

    config = load_orm_config(env)
    database = Database(config)

    with database.get_session() as session:
        validate_all(session, print_errors)



@eorm.command()
@click.option("-e", "--env", type=str, help="Path to .env file for environment configuration")
def zarr_tree(env):
    """Display the structure of the zarr store, showing groups and array shapes."""
    import zarr
    
    from eyened_orm import Database
    
    config = load_orm_config(env)
    database = Database(config)
    
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
@click.option("-e", "--env", type=str, help="Path to .env file for environment configuration")
@click.option("--new-store-path", type=click.Path(), required=True, help="Path to the new zarr store directory")
def defragment_zarr(env, new_store_path):
    """Defragment the zarr store by copying all segmentations to a new store with sequential indices.
    
    This command creates a new zarr store and copies all existing segmentations to it,
    assigning new sequential ZarrArrayIndex values to eliminate gaps and improve storage efficiency.
    The ZarrArrayIndex values in the database will be updated to reflect the new indices.
    """
    from pathlib import Path
    
    from orm.eyened_orm.utils.zarr.manager import ZarrStorageManager
    
    config = load_orm_config(env)
    
    
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
@click.option("-e", "--env", type=str, help="Path to .env file for environment configuration")
@click.option("--print-errors", is_flag=True, default=False, help="Print errors for failed hash calculations")
def update_hashes(env, print_errors):
    """Update FileChecksum and DataHash for all ImageInstances in the database where they are NULL.

    This command will iterate over all ImageInstances in the database with FileChecksum == None
    or DataHash == None and populate them with the outputs of im.calc_file_checksum() and 
    im.calc_data_hash() respectively.
    """
    from eyened_orm import Database, ImageInstance
    from sqlalchemy import select

    config = load_orm_config(env)
    database = Database(config)

    with database.get_session() as session:
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
