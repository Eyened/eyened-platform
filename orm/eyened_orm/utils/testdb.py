import subprocess


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
        "-p" + db_config.password.get_secret_value(),
    ]
    if include_database:
        result.append(db_config.database)
    return [str(arg) for arg in result]


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
