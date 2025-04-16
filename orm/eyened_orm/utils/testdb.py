from pathlib import Path
import subprocess
import tempfile

import mysql.connector


# These tables will be dumped partially using smartdump
# Only the rows related to the smartdump query will be dumped
# The rest of the tables will be dumped fully
partial_tables = set(
    [
        "Patient",
        "Study",
        "Series",
        "Annotation",
        "FormAnnotation",
        "ImageInstance",
        "AnnotationData",
        "Task",
        "SubTask",
        "SubTaskImageLink",
    ]
)


def dump_database(db_config, dump_file, no_data=False, no_create=False, tables=None):
    source_db_string = (
        f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
    )

    if tables is None:
        tables = []

    command = [
        "mysqldump",
        "--skip-triggers",
        "--no-data" if no_data else "",
        "--no-create-info" if no_create else "",
        "-h",
        db_config["host"],
        "-P",
        db_config["port"],
        "-u",
        db_config["user"],
        "-p" + db_config["password"],  # password without space
        db_config["database"],
        *tables,
    ]
    command = [tk for tk in command if tk != ""]

    print(f"Dumping database {source_db_string}")
    print(" ".join(command))
    # Run the command and save the output to the specified dump file
    # with open(dump_file, "w") as f:
    result = subprocess.run(command, stdout=dump_file, stderr=subprocess.PIPE)

    if result.returncode == 0:
        print(f"Database dumped successfully into {dump_file.name}.")
    else:
        print("Error occurred during dumping the database.")
        print(result.stderr)
        return False


def drop_create_db(test_db):
    sql_commands = f"""
DROP DATABASE IF EXISTS `{test_db["database"]}`;
CREATE DATABASE `{test_db["database"]}`;
"""
    command = [
        "mysql",
        "-h",
        test_db["host"],
        "-P",
        test_db["port"],
        "-u",
        test_db["user"],
        "-p" + test_db["password"],
    ]

    print("Dropping and creating the database..")
    print(" ".join(command))
    result = subprocess.run(
        command, input=sql_commands, stderr=subprocess.PIPE, text=True, check=True
    )

    if result.returncode == 0:
        print("Database dropped and created successfully.")
    else:
        print("Error occurred during dropping and creating the database.")
        print(result.stderr)
        return False


def load_db(db_config, dump_file, force=False):
    # now load the dump file
    command = [
        "mysql",
        "-h",
        db_config["host"],
        "-P",
        db_config["port"],
        "-u",
        db_config["user"],
        "-p" + db_config["password"],
        "--force" if force else "",
        db_config["database"],
    ]

    command = [tk for tk in command if tk != ""]
    command_string = " ".join(command)

    print("Loading database from dump.")
    print(command_string)

    # Execute the load command and pass the dump file
    result = subprocess.run(command, stdin=dump_file, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:
        print("Database loaded successfully.")
    else:
        print("Error occurred during loading the database.")
        print(result.stderr)
        return False


def get_table_names(db_config):
    import mysql.connector
    # Connect to the MySQL database
    connection = mysql.connector.connect(
        host=db_config["host"],
        port=db_config["port"],
        user=db_config["user"],
        password=db_config["password"],
        database=db_config["database"],
    )

    try:
        # Create a cursor object
        cursor = connection.cursor()

        # Query to get all table names
        cursor.execute("SHOW TABLES")

        # Fetch and print all table names
        tables = cursor.fetchall()
        return [table[0] for table in tables]

    finally:
        # Close the connection
        cursor.close()
        connection.close()


def run_smartdump(db_config, dump_file):
    smartdump_path = (
        Path.home() / ".config/composer/vendor/benmorel/smartdump/bin/smartdump"
    )

    # dump the partial tables using smartdump
    database = db_config["database"]
    command = [
        str(smartdump_path),
        "--host",
        db_config["host"],
        "--user",
        db_config["user"],
        "--port",
        db_config["port"],
        "--password",
        db_config["password"],
        "--no-create-table",
        f'"{database}.Annotation:WHERE PatientID=217250"',
        f'"{database}.FormAnnotation:WHERE PatientID=217250"',
        f"\"{database}.AnnotationData:WHERE DatasetIdentifier LIKE '217250%'\"",
        f'"{database}.SubTaskImageLink:WHERE SubTaskID=8908"',
        f'"{database}.AnnotationData:WHERE AnnotationID=1926813"',
    ]

    command_string = " ".join(command)
    print(command_string)

    # Execute the load command and pass the dump file
    result = subprocess.run(
        command_string, stdout=dump_file, stderr=subprocess.PIPE, shell=True
    )

    if result.returncode == 0:
        print("Database loaded successfully.")
    else:
        print("Error occurred during loading the database.")
        print(result.stderr)


def populate(source_db, test_db):
    all_tables = get_table_names(source_db)
    full_tables = list(set(all_tables) - partial_tables)

    # load the full tables
    with tempfile.NamedTemporaryFile(mode='w+t') as dump_file:
        dump_database(source_db, dump_file, no_create=True, tables=full_tables)
        dump_file.seek(0)
        load_db(test_db, dump_file)

    # load the partial tables
    with tempfile.NamedTemporaryFile(mode='w+t') as dump_file:
        run_smartdump(source_db, dump_file)
        dump_file.seek(0)
        load_db(test_db, dump_file, force=True)