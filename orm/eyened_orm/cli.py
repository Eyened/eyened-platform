import click
import json

from .utils.testdb import drop_create_db, load_db
from tqdm import tqdm

from .commands.shared import get_database
from .commands.targets import image_target_options, has_target_spec, resolve_image_target, target_spec_from_cli
from .utils.env import load_env_file

"""
Command utilities for the eyened ORM.

The following commands are available:
- update-thumbnails: Update thumbnails for all images in the database.
- clean-thumbnails: Remove dangling thumbnail files and report broken ThumbnailPath refs.
- run-cfi-models: Run CFI attribute inference models (cfi-roi, cfi-keypoints, cfi-odfd, cfi-quality).
- run-models: Deprecated alias for run-cfi-models.
- run-etdrs-model: Run ETDRS model processing on segmentations.
- run-registration: Pairwise CFI/AF/IR registration per patient; scope with --patient or --project.
- seed-form-schemas: Insert builtin viewer FormSchema rows (ETDRS grid, registration).
- validate-forms: Validate form annotations and schemas in the database.
- zarr-tree: Display the structure of the zarr store, showing groups and array shapes.
- defragment-zarr: Defragment the zarr store by copying all segmentations to a new store with sequential indices.
- update-hashes: Update FileChecksum and DataHash for ImageInstances where they are NULL.
- load-dump: Load a database dump file, replacing the entire database.
- init-admin: Create or promote the administrator account (idempotent).
- grant: Grant or change a project role for a user.
- revoke: Remove a user's membership from a project, or from every project with --all.
- grant-for-task: Grant every project a set of tasks touch, after review.
- grant-all: Cutover step 3 -- grant every authenticating creator a role in every project.
- set-admin: Set or clear administrator status on an existing account.
- set-password: Set an existing user's password.
- deactivate: Revoke all of a user's memberships.
- reactivate: Restore a deactivated user's memberships.

Important: import packages that are not dependencies of the ORM within the function definitions, as they are not installed by default.
"""


@click.group(name="eorm")
@click.option(
    "--env-file",
    "-e",
    type=click.Path(exists=True, dir_okay=False),
    required=False,
    help="Path to a .env file to load for this command",
)
def eorm(env_file):
    load_env_file(env_file, override=True)


def _run_mysqlsh(db_config, expression: str):
    import subprocess

    cmd = [
        "mysqlsh",
        "--uri",
        f"{db_config.user}@{db_config.host}:{db_config.port}",
        "--passwords-from-stdin",
        "--py",
        "-e",
        expression,
    ]
    subprocess.run(
        cmd,
        input=f"{db_config.password.get_secret_value()}\n",
        text=True,
        check=True,
    )


def _register_model_commands():
    from .commands.model_processing import model_commands

    for command in model_commands:
        eorm.add_command(command)


_register_model_commands()


def _register_rbac_commands():
    from .commands.rbac import rbac_commands

    for command in rbac_commands:
        eorm.add_command(command)


_register_rbac_commands()


@eorm.command()
@click.option("--recreate", is_flag=True, default=False, help="Drop and create the database before creating the models")
@click.option(
    "--seed-form-schemas",
    is_flag=True,
    default=False,
    help="Also insert builtin viewer FormSchema rows after creating tables",
)
def initialize_database(recreate: bool, seed_form_schemas: bool):
    """Initialize an empty database by running the migration trail to head."""
    print("Initializing database...")
    database = get_database(confirmation=True)
    db_config = database.database_settings

    if recreate:
        print("Recreating empty database (drop if exists)...")
        if not drop_create_db(db_config):
            raise click.ClickException("Failed to recreate empty database.")

    print("Running migrations...")
    from eyened_orm.utils.alembic_utils import upgrade_to_head

    head = upgrade_to_head(database.engine)
    print(f"Database is at Alembic head ({head}).")

    if seed_form_schemas:
        _run_seed_form_schemas(database, update=False)


def _run_seed_form_schemas(database, update: bool) -> None:
    from .form_schemas import seed_form_schemas

    with database.get_session() as session:
        result = seed_form_schemas(session, update=update)

    if result.created:
        print(f"Created: {', '.join(result.created)}")
    if result.updated:
        print(f"Updated: {', '.join(result.updated)}")
    if result.skipped:
        print(f"Skipped (already present): {', '.join(result.skipped)}")
    if not result.created and not result.updated and not result.skipped:
        print("No builtin form schemas configured.")


@eorm.command("seed-form-schemas")
@click.option(
    "--update",
    is_flag=True,
    default=False,
    help="Update Schema JSON and EntityType for existing builtin schemas",
)
def seed_form_schemas_cmd(update: bool):
    """Insert builtin viewer FormSchema rows (ETDRS grid, registration schemas)."""
    database = get_database()
    _run_seed_form_schemas(database, update=update)


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
        except ValueError as e:
            raise click.ClickException(str(e)) from e
        session.commit()
    click.echo("User created successfully")


@eorm.command()
@image_target_options(require_one=False)
@click.option("--failed", is_flag=True, default=False)
@click.option("--print-errors", is_flag=True, default=False)
def update_thumbnails(
    path,
    image_ids,
    project,
    patient,
    exclude,
    modality,
    include_inactive,
    failed,
    print_errors,
):
    """Update thumbnails for images in the database.

    With no target flags, scans the whole database for missing thumbnails.
    With --path, --image-ids, --project, or --patient, updates only that scope.
    """

    from eyened_orm.importer.thumbnails import (
        run_update_thumbnails_for_image_ids_job,
        run_update_thumbnails_job,
    )

    database = get_database()
    spec = target_spec_from_cli(
        path=path,
        image_ids=image_ids,
        project=project,
        patient=patient,
        exclude=exclude,
        modality=modality,
        include_inactive=include_inactive,
    )

    if has_target_spec(spec):
        with database.get_session() as session:
            target = resolve_image_target(session, spec)
            print(f"Target: {target.summary}")
            run_update_thumbnails_for_image_ids_job(
                database,
                sorted(target.image_ids),
                print_errors=print_errors,
            )
    else:
        run_update_thumbnails_job(
            database, include_failed=failed, print_errors=print_errors
        )


@eorm.command("clean-thumbnails")
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Delete dangling thumbnail files (default is dry-run / report only)",
)
@click.option(
    "--print-limit",
    type=int,
    default=50,
    show_default=True,
    help="Max dangling files / broken refs to print",
)
def clean_thumbnails_cmd(apply: bool, print_limit: int):
    """Remove dangling thumbnail files and report broken ThumbnailPath refs.

    Compares ``{EYENED_STORAGE_ROOT}/thumbnails/`` to non-empty
    ``ImageInstance.ThumbnailPath`` values:

    - Deletes (with ``--apply``) on-disk ``_144.jpg`` / ``_540.jpg`` files that
      are not indexed in the database.
    - Lists ImageInstance rows whose ThumbnailPath is set but at least one size
      file is missing.

    Default is dry-run: report only, no deletions.
    """
    from eyened_orm.importer.thumbnails import run_clean_thumbnails_job

    database = get_database(confirmation=apply)
    run_clean_thumbnails_job(database, apply=apply, print_limit=print_limit)


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

    from eyened_orm.segmentation_storage import get_zarr_storage_manager

    manager = get_zarr_storage_manager()
    store_path = manager.store_path

    try:
        root = zarr.open_group(store=store_path, mode="r")
    except Exception as e:
        print(f"Error opening zarr store at {store_path}: {e}")
        return

    print(f"Zarr store: {store_path}")
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

    from eyened_orm.segmentation_storage import get_zarr_storage_manager
    from eyened_orm.utils.zarr.manager import ZarrStorageManager

    manager = get_zarr_storage_manager()
    store_path = manager.store_path

    new_store_path = Path(new_store_path)
    new_store_path.mkdir(parents=True, exist_ok=True)

    old_manager = ZarrStorageManager(store_path)

    print(f"Defragmenting zarr store from: {store_path}")
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
@image_target_options(require_one=False)
@click.option(
    "--print-errors",
    is_flag=True,
    default=False,
    help="Print errors for failed hash calculations",
)
def update_hashes(
    path,
    image_ids,
    project,
    patient,
    exclude,
    modality,
    include_inactive,
    print_errors,
):
    """Update FileChecksum and DataHash for ImageInstances where they are NULL.

    With no target flags, scans the whole database. With target flags, limits scope.
    """
    from eyened_orm import ImageInstance
    from sqlalchemy import select

    database = get_database()
    spec = target_spec_from_cli(
        path=path,
        image_ids=image_ids,
        project=project,
        patient=patient,
        exclude=exclude,
        modality=modality,
        include_inactive=include_inactive,
    )

    with database.get_session() as session:
        query = select(ImageInstance).filter(
            (ImageInstance.FileChecksum == None) | (ImageInstance.DataHash == None)
        )
        if has_target_spec(spec):
            target = resolve_image_target(session, spec)
            print(f"Target: {target.summary}")
            query = query.filter(
                ImageInstance.ImageInstanceID.in_(target.image_ids)
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
    help="Path to dump directory (default) or SQL file with --legacy-sql",
)
@click.option(
    "--legacy-sql",
    is_flag=True,
    default=False,
    help="Use legacy SQL file loader instead of mysqlsh dump directory loader",
)
@click.option(
    "--reset-progress",
    is_flag=True,
    default=False,
    help="Force mysqlsh load from scratch by discarding existing load progress.",
)
def load_dump(dump_path, legacy_sql, reset_progress):
    """Load a database dump, replacing the entire database.

    This command will:
    1. Drop and recreate the database (clearing all data)
    2. Load a mysqlsh dump directory (default) or SQL file (--legacy-sql)

    WARNING: This will permanently delete all existing data in the database.
    """
    from pathlib import Path

    dump_path = Path(dump_path)

    print(f"Loading database dump from: {dump_path}")
    print("WARNING: This will replace the entire database!")
    print("=" * 60)

    database = get_database(confirmation=True)
    db_config = database.database_settings

    if not dump_path.exists():
        print(f"Error: Dump path not found: {dump_path}")
        return

    print("Confirmation received. Proceeding with database load...\n")

    # Drop and recreate the database
    print("Clearing database...")
    if not drop_create_db(db_config):
        print("Error: Failed to clear database")
        return

    if legacy_sql:
        if dump_path.is_dir():
            print("Error: --legacy-sql expects --dump-path to be a .sql file")
            return

        print("\nLoading SQL dump file...")
        with open(dump_path, "r", encoding="utf-8") as dump_file:
            if not load_db(db_config, dump_file, force=True):
                print("Error: Failed to load database dump")
                return
    else:
        import subprocess

        if not dump_path.is_dir():
            print(
                "Error: mysqlsh mode expects --dump-path to be a dump directory. "
                "Use --legacy-sql for .sql files."
            )
            return

        print("\nLoading mysqlsh dump directory...")
        load_options = {"threads": 4}
        if reset_progress:
            load_options["resetProgress"] = True
        load_expr = (
            f"util.load_dump({json.dumps(str(dump_path))}, {repr(load_options)})"
        )
        try:
            _run_mysqlsh(db_config, load_expr)
        except FileNotFoundError:
            print(
                "Error: mysqlsh is not installed. Use --legacy-sql or install MySQL Shell."
            )
            return
        except subprocess.CalledProcessError as exc:
            print(f"Error: mysqlsh load failed with exit code {exc.returncode}")
            return

    print("\nDatabase dump loaded successfully!")


@eorm.command()
@click.option(
    "--dump-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help="Directory to write the dated dump folder (or SQL file with --legacy-sql)",
)
@click.option(
    "--legacy-sql",
    is_flag=True,
    default=False,
    help="Use legacy mysqldump SQL file output instead of mysqlsh compact dump directory",
)
def save_dump(dump_dir, legacy_sql):
    """Save a dated database dump to the given directory."""
    from datetime import datetime
    import os
    from pathlib import Path
    import subprocess
    import tempfile

    database = get_database()
    db_config = database.database_settings

    dump_dir = Path(dump_dir)
    date_stamp = datetime.now().strftime("%Y_%m_%d")
    dump_path = dump_dir / f"eyened_db_dump_{date_stamp}"
    if legacy_sql:
        dump_path = dump_path.with_suffix(".sql")

    print(f"Saving database dump to: {dump_path}")
    print(f"Source database: {db_config.database} on {db_config.host}:{db_config.port}")

    if legacy_sql:
        defaults_file_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", delete=False
            ) as defaults_file:
                defaults_file_path = defaults_file.name
                defaults_file.write(
                    "[client]\n"
                    f"user={db_config.user}\n"
                    f"password={db_config.password.get_secret_value()}\n"
                    f"host={db_config.host}\n"
                    f"port={db_config.port}\n"
                )
            os.chmod(defaults_file_path, 0o600)

            dump_cmd = [
                "mysqldump",
                f"--defaults-extra-file={defaults_file_path}",
                "--single-transaction",
                "--routines",
                db_config.database,
            ]

            with open(dump_path, "w", encoding="utf-8") as dump_file:
                subprocess.run(dump_cmd, stdout=dump_file, check=True)
        except subprocess.CalledProcessError as exc:
            print(f"Error: mysqldump failed with exit code {exc.returncode}")
            return
        finally:
            if defaults_file_path and os.path.exists(defaults_file_path):
                os.remove(defaults_file_path)
    else:
        if dump_path.exists():
            print(f"Error: Dump directory already exists: {dump_path}")
            return

        dump_options = {"threads": 4, "compression": "zstd"}
        dump_expr = (
            f"util.dump_schemas({json.dumps([db_config.database])}, "
            f"{json.dumps(str(dump_path))}, {json.dumps(dump_options)})"
        )
        try:
            _run_mysqlsh(db_config, dump_expr)
        except FileNotFoundError:
            print(
                "Error: mysqlsh is not installed. Use --legacy-sql or install MySQL Shell."
            )
            return
        except subprocess.CalledProcessError as exc:
            print(f"Error: mysqlsh dump failed with exit code {exc.returncode}")
            return

    print("Database dump saved successfully!")
