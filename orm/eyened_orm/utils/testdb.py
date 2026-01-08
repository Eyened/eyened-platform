from dataclasses import asdict
import os
import subprocess
import tempfile
import mysql.connector
from eyened_orm.utils.smart_dump import DatabaseDumper
from eyened_orm.utils.paths import paths


def build_command(command, db_config, args=[], include_database=True):
    result = [
        command,
        *args,
        "-h",
        db_config.host,
        "-P",
        db_config.port,
        "-u",
        db_config.user,
        "-p" + db_config.password,
    ]
    if include_database:
        result.append(db_config.database)
    return [str(arg) for arg in result]


def dump_database(db_config, dump_file, no_data=False, no_create=False, tables=[]):
    args = ["--skip-triggers"]
    if no_data:
        args.append("--no-data")
    if no_create:
        args.append("--no-create-info")

    args += [
        '--ignore-table=eyened_database.ProjectToImageInstance',
        '--ignore-table=eyened_database.Statistics'
    ]

    command = build_command("mysqldump", db_config, args) + tables

    result = subprocess.run(command, stdout=dump_file, stderr=subprocess.PIPE)

    if result.returncode == 0:
        print(f"Database dumped successfully into {dump_file.name}.")
        return True
    else:
        print("Error occurred during dumping the database.")
        print(result.stderr)
        return False


def drop_create_db(test_db):
    db = test_db.database
    sql_commands = f"DROP DATABASE IF EXISTS `{db}`;CREATE DATABASE `{db}`;"
    command = build_command("mysql", test_db, include_database=False)

    print("Creating empty database")
    print(" ".join(command))
    result = subprocess.run(
        command, input=sql_commands, stderr=subprocess.PIPE, text=True, check=True
    )

    if result.returncode == 0:
        print("Database created successfully.")
        return True
    else:
        print("Error occurred during creating the database.")
        print(result.stderr)
        return False


def load_db(db_config, dump_file, force=False):
    args = ["--force"] if force else []
    command = build_command("mysql", db_config, args)

    print("Loading database from dump.")
    result = subprocess.run(command, stdin=dump_file, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:
        print("Database loaded successfully.")
        return True
    else:
        print("Error occurred during loading the database.")
        print(result.stderr)
        return False


def stream_mirror_database(
    source_db,
    target_db,
    *,
    include_routines: bool = True,
    include_triggers: bool = True,
    include_events: bool = True,
    force: bool = False,
    extra_mysqldump_args: list[str] | None = None,
):
    """Stream a full logical copy from source to target using `mysqldump | mysql`.

    This avoids intermediate dump files and any Python-side SQL generation.
    Assumes the target database already exists.
    """

    mysqldump_args: list[str] = [
        "--single-transaction",
        "--quick",
        "--hex-blob",
        "--set-gtid-purged=OFF",
    ]
    if include_routines:
        mysqldump_args.append("--routines")
    if include_triggers:
        mysqldump_args.append("--triggers")
    if include_events:
        mysqldump_args.append("--events")
    if extra_mysqldump_args:
        mysqldump_args.extend(extra_mysqldump_args)

    mysql_args: list[str] = ["--force"] if force else []

    def _build_cli_cmd(command: str, db_config, args: list[str]) -> list[str]:
        # Do NOT pass passwords on the command line. Use MYSQL_PWD env var per-process.
        return [
            str(x)
            for x in (
                [
                    command,
                    *args,
                    "--protocol=tcp",
                    "-h",
                    db_config.host,
                    "-P",
                    db_config.port,
                    "-u",
                    db_config.user,
                    db_config.database,
                ]
            )
        ]

    dump_cmd = _build_cli_cmd("mysqldump", source_db, mysqldump_args)
    load_cmd = _build_cli_cmd("mysql", target_db, mysql_args)

    print("Streaming database mirror:")
    print("  dump:", " ".join(dump_cmd))
    print("  load:", " ".join(load_cmd))

    dump_env = os.environ.copy()
    dump_env["MYSQL_PWD"] = str(source_db.password)
    load_env = os.environ.copy()
    load_env["MYSQL_PWD"] = str(target_db.password)

    dump_proc = subprocess.Popen(
        dump_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        env=dump_env,
    )
    try:
        load_proc = subprocess.Popen(
            load_cmd,
            stdin=dump_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=False,
            env=load_env,
        )
    finally:
        # Parent must close its copy of the pipe so load_proc can see EOF.
        if dump_proc.stdout is not None:
            dump_proc.stdout.close()

    _, load_err = load_proc.communicate()
    dump_err = b""
    try:
        # Ensure mysqldump also completes and collect its stderr.
        _, dump_err = dump_proc.communicate()
    except Exception:
        dump_proc.kill()
        raise

    if dump_proc.returncode != 0 or load_proc.returncode != 0:
        dump_err_text = (dump_err or b"").decode(errors="replace")
        load_err_text = (load_err or b"").decode(errors="replace")

        hint = ""
        if "Can't connect to MySQL server" in dump_err_text or "Got error: 2003" in dump_err_text:
            hint = (
                "\nHint: mysqldump could not reach the SOURCE host/port. "
                "Check VPN/firewall/DNS/port-forwarding, or run this command from a machine "
                "that can reach the source MySQL server (or via an SSH tunnel).\n"
            )

        raise RuntimeError(
            "Database mirror failed.\n"
            f"mysqldump exit={dump_proc.returncode}\n"
            f"mysql exit={load_proc.returncode}\n"
            f"mysqldump stderr:\n{dump_err_text}\n"
            f"mysql stderr:\n{load_err_text}\n"
            f"{hint}"
        )

    # Avoid printing stdout unless needed; it can be large/noisy.
    return True


class DatabaseTransfer:
    def __init__(self, source_db, test_db):
        self.source_db = source_db
        self.test_db = test_db

    def create_test_db(self, no_data=True):
        """Create a test database from the source database.

        Args:
            no_data (bool): If True, the database will be created without data.

        """

        drop_create_db(self.test_db)

        with tempfile.NamedTemporaryFile(mode="w+t") as dump_file:
            dump_database(self.source_db, dump_file, no_data=no_data)
            dump_file.seek(0)
            load_db(self.test_db, dump_file)

    def populate(self, copy_objects: list):

        dumper = DatabaseDumper(self.source_db, paths, copy_objects)
        sql_statements = dumper.dump()

        conn = mysql.connector.connect(**asdict(self.source_db))
        with conn.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version;")
            version = cursor.fetchone()[0]

        conn = mysql.connector.connect(**asdict(self.test_db))
        with conn.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO alembic_version (version_num) VALUES ('{version}');"
            )
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            for sql, values in sql_statements:
                try:
                    cursor.execute(sql, values)
                except mysql.connector.DatabaseError as e:
                    # doesn't handle INSERT IGNORE well apparently
                    pass
            conn.commit()
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.close()
