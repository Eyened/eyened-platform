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

        conn = mysql.connector.connect(**self.source_db.model_dump())
        with conn.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version;")
            version = cursor.fetchone()[0]

        

        conn = mysql.connector.connect(**self.test_db.model_dump())
        with conn.cursor() as cursor:
            cursor.execute(f"INSERT INTO alembic_version (version_num) VALUES ('{version}');")
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
