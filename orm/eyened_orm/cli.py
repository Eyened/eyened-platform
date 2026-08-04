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
- run-models: Run attribute inference models (cfi-roi, cfi-keypoints, cfi-odfd, cfi-quality) on a set of image IDs.
- run-etdrs-model: Run ETDRS model processing on segmentations.
- run-cfi-amd: Run CFI AMD segmentation models.
- run-registration: Pairwise CFI/AF/IR registration per patient; scope with --patient or --project.
- seed-form-schemas: Insert builtin viewer FormSchema rows (ETDRS grid, registration).
- validate-forms: Validate form annotations and schemas in the database.
- zarr-tree: Display the structure of the zarr store, showing groups and array shapes.
- defragment-zarr: Defragment the zarr store by copying all segmentations to a new store with sequential indices.
- update-hashes: Update FileChecksum and DataHash for ImageInstances where they are NULL.
- load-dump: Load a database dump file, replacing the entire database.
- init-admin: Create or promote a system_admin (idempotent); run before enabling RBAC enforcement.
- backfill-task-projects: Anchor each task to the project its images prove; park the rest.
- task-projects: Show which projects a task's images belong to (read-only).

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


@eorm.command()
@click.option("--recreate", is_flag=True, default=False, help="Drop and create the database before creating the models")
@click.option(
    "--seed-form-schemas",
    is_flag=True,
    default=False,
    help="Also insert builtin viewer FormSchema rows after creating tables",
)
def initialize_database(recreate: bool, seed_form_schemas: bool):
    """Initialize an empty database and create ORM tables."""
    from eyened_orm.base import Base

    print("Initializing database...")
    database = get_database(confirmation=True)
    db_config = database.database_settings

    if recreate:
        print("Recreating empty database (drop if exists)...")
        if not drop_create_db(db_config):
            raise click.ClickException("Failed to recreate empty database.")

    print("Creating tables...")
    Base.metadata.create_all(database.engine)

    from eyened_orm.utils.alembic_utils import (
        get_current_alembic_revision,
        stamp_alembic_head,
    )

    current = get_current_alembic_revision(database.engine)
    head = stamp_alembic_head(database.engine)
    if current == head:
        print(f"Alembic already at head ({head}).")
    else:
        print(f"Stamped Alembic at head ({head}).")

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
            session.commit()
            print(f"User created successfully")
        except ValueError as e:
            print(f"Error creating user: {e}")


@eorm.command()
@click.option("--username", type=str, prompt=True, envvar="EYENED_API_ADMIN_USERNAME")
@click.option(
    "--password",
    type=str,
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
)
def init_admin(username: str, password: str):
    """Create or promote a system_admin (idempotent).

    Bootstrap must run before RBAC enforcement is switched on: granting a role
    requires an existing admin, so the first one is seeded here.

    Safe to re-run -- an account that is already an active admin is left
    untouched, password included, and reports so without prompting. The
    password just typed is used ONLY to create a brand-new account: promoting
    a pre-existing account or reactivating a deactivated one keeps that
    account's existing password, which is why the promote case asks for
    confirmation before it commits.
    """

    # Echo it: --username carries envvar=EYENED_API_ADMIN_USERNAME, so a shell
    # that sourced the server's .env supplies the name and click skips the
    # prompt entirely. The operator must still see which account this is about.
    click.echo(f"Bootstrapping system admin account: '{username}'")

    from eyened_orm import is_system_admin
    from eyened_orm.repositories.creator_repository import CreatorRepository
    from eyened_orm.utils.db_users import BootstrapOutcome, ensure_admin

    database = get_database()
    with database.get_session() as session:
        # Confirm BEFORE anything is written, and only for a genuine promote.
        # This is the one case a human must approve: the account already
        # existed, it keeps its existing password, and /auth/register is
        # unauthenticated -- so the row may have been placed there by someone
        # else, who would still be able to log in as the admin afterwards.
        # Bootstrap never demotes (§3.7), so a wrong promote is undoable only by
        # hand-written SQL.
        #
        # Deliberately ahead of ensure_admin, not between it and the commit:
        # ensure_admin's promote branch flushes, so prompting after it would
        # block on human input while an UPDATE Creator SET Role=1 holds an
        # EXCLUSIVE InnoDB row lock on the admin's row -- every other writer of
        # that row waits for as long as the operator is away from the terminal.
        # (Being "idle in transaction" is not the distinguishing factor: the
        # pre-state probe below opens a read transaction across the prompt
        # either way. Holding a write lock across it is.) And exceeding MySQL's
        # wait_timeout would fail the commit AFTER the operator already
        # answered "y" (pool_pre_ping validates on checkout, not mid-use),
        # losing a bootstrap the human had approved -- whereas aborting this
        # way, before anything is written, loses nothing.
        #
        # `existing is not None and not is_system_admin(existing)` is exactly
        # ensure_admin's `promoted` predicate -- NOT the existence test that
        # 033b6ee got wrong, which fired on the benign re-run too.
        existing = CreatorRepository(session).get_by_name(username)
        if existing is not None and not is_system_admin(existing):
            click.confirm(
                f"\n'{existing.CreatorName}' is a PRE-EXISTING account "
                f"(CreatorID={existing.CreatorID}, created "
                f"{existing.DateInserted.date()}) and is not currently a system "
                f"admin.\nPromoting it grants full data access to every "
                f"project. Its EXISTING password is kept -- the password you "
                f"just typed is discarded.\nPromote this account?",
                abort=True,
            )

        # reactivate=True, unlike the dev bypass's default False: a human
        # running the recovery command by hand IS the consent, and this is the
        # only command that can rescue a deployment whose sole admin was
        # deactivated.
        admin, outcome = ensure_admin(
            session, username, password, reactivate=True
        )
        session.commit()

        if outcome is BootstrapOutcome.created:
            print(
                f"Created system admin '{admin.CreatorName}' "
                f"(CreatorID={admin.CreatorID})."
            )
        elif outcome is BootstrapOutcome.promoted:
            report = (
                f"Promoted PRE-EXISTING account '{admin.CreatorName}' "
                f"(CreatorID={admin.CreatorID}) to system_admin. Its password "
                f"was NOT changed."
            )
            # The promote branch returns before the reactivate branch, so an
            # account that was both a non-admin AND deactivated is promoted
            # with Inactive still set. Deliberate -- but reporting only the
            # promotion would be reporting success while leaving an admin who
            # cannot log in once deactivation is enforced, from the one command
            # that exists to recover a deployment. Name the remaining step.
            if admin.Inactive:
                report += (
                    " It is still DEACTIVATED and will not be able to log in "
                    "once deactivation is enforced -- re-run this command to "
                    "reactivate it (it is a system admin now, so that run "
                    "needs no confirmation)."
                )
            print(report)
        elif outcome is BootstrapOutcome.reactivated:
            print(
                f"Reactivated system admin '{admin.CreatorName}' "
                f"(CreatorID={admin.CreatorID}). Its password was NOT changed."
            )
        elif outcome is BootstrapOutcome.unchanged:
            print(
                f"'{admin.CreatorName}' (CreatorID={admin.CreatorID}) is "
                f"already a system admin; nothing changed."
            )
        else:
            # A fifth BootstrapOutcome must not fall through to "nothing
            # changed": the commit above has already happened, so that line
            # would report an outcome that did not occur -- the exact defect
            # this dispatch was rewritten to remove. Fail loudly instead.
            raise click.ClickException(
                f"Unhandled bootstrap outcome {outcome!r} for "
                f"'{admin.CreatorName}' (CreatorID={admin.CreatorID}). The "
                f"change was already committed; inspect the account by hand."
            )


@eorm.command("backfill-task-projects")
@click.option("--dry-run", is_flag=True, default=False, help="Report and write nothing")
@click.option("--yes", is_flag=True, default=False, help="Skip the confirmation prompt")
@click.option(
    "--sentinel-name",
    # The ONE place this name may be spelled. No runtime code resolves the
    # sentinel -- not by name, id or settings -- which is why apply_backfill
    # takes it as a parameter rather than importing a constant.
    default="_unresolved_legacy_tasks",
    show_default=True,
    help="Project that holds tasks whose anchor cannot be determined",
)
def backfill_task_projects(dry_run: bool, yes: bool, sentinel_name: str):
    """Anchor each task to the project its images prove; park the rest.

    An existing-deployment tool: fresh deployments build Task.ProjectID NOT NULL
    directly and never run this. Run it between the two Task.ProjectID
    revisions -- the column must exist and must not be NOT NULL yet.
    """
    from eyened_orm.utils.task_projects import apply_backfill, plan_backfill

    database = get_database()
    with database.get_session() as session:
        plan = plan_backfill(session)

        click.echo(f"Anchorable (one provable project): {len(plan.anchored)}")
        click.echo(f"To park (ambiguous or no image evidence): {len(plan.to_park)}")
        if plan.to_park:
            click.echo(f"  task ids: {plan.to_park}")
            click.echo(f"  sentinel project: '{sentinel_name}'")

        if not plan.anchored and not plan.to_park:
            click.echo("Nothing to do -- every task already has a project.")
            return

        if dry_run:
            click.echo("--dry-run: nothing written.")
            return

        if not yes:
            click.confirm("Apply?", abort=True)

        report = apply_backfill(session, plan, sentinel_name=sentinel_name)
        session.commit()

        click.echo(f"Anchored {report.anchored} task(s); parked {report.parked}.")
        if report.sentinel_created:
            click.echo(
                f"Created sentinel project '{sentinel_name}' "
                f"(ProjectID={report.sentinel_project_id}). It has no members by "
                f"design; deleting it would delete the tasks it holds."
            )


@eorm.command("task-projects")
@click.argument("taskid", type=int)
@click.option("--for", "for_username", type=str, default=None,
              help="Mark which of these projects the named user already belongs to")
@click.option("--sentinel-name", default="_unresolved_legacy_tasks", show_default=True)
def task_projects(taskid: int, for_username: str | None, sentinel_name: str):
    """Show which projects a task's images belong to. Read-only."""
    from eyened_orm.repositories.creator_repository import CreatorRepository
    from eyened_orm.utils.task_projects import project_breakdown

    database = get_database()
    with database.get_session() as session:
        creator_id = None
        if for_username is not None:
            # Validate BEFORE the breakdown prints: unvalidated, a typo marks
            # every project MISSING, which is indistinguishable from a user with
            # no access at all -- and that skews the anchor choice.
            creator = CreatorRepository(session).get_by_name(for_username)
            if creator is None:
                raise click.ClickException(f"No such user: {for_username!r}")
            creator_id = creator.CreatorID

        try:
            report = project_breakdown(
                session, taskid, sentinel_name=sentinel_name, for_creator_id=creator_id
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

        parked = "  (PARKED)" if report.parked else ""
        click.echo(
            f"Task {report.task_id} {report.task_name!r}  --  "
            f"{report.anchor_project_name}{parked}"
        )
        for usage in report.usage:
            marker = ""
            if usage.member is not None:
                marker = (
                    f"   {for_username}: member"
                    if usage.member
                    else f"   {for_username}: MISSING"
                )
            click.echo(
                f"  {usage.project_id:>4}  {usage.project_name:<24} "
                f"{usage.subtasks:>6} subtasks {usage.links:>6} links{marker}"
            )
        if not report.usage:
            click.echo("  (no image evidence)")


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
