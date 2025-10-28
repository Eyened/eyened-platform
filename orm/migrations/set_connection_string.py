import sys
from pathlib import Path

if __name__ == "__main__":
    # Check if path argument is provided
    if len(sys.argv) < 2:
        print("Usage: python set_connection_string.py <path_to_env_file>")
        print("Example: python set_connection_string.py ../../dev/.env")
        sys.exit(1)

    env_path = Path(sys.argv[1]).resolve()

    if not env_path.exists():
        print(f"Error: Environment file not found at {env_path}")
        sys.exit(1)

    print(f"Loading environment from: {env_path}")
    from dotenv import dotenv_values

    env = dotenv_values(dotenv_path=env_path)
    # Extract required values from the provided .env file (no process env mutation)
    try:
        user = env["DATABASE_USER"]
        password = env["DATABASE_PASSWORD"]
        host = env["DATABASE_HOST"]
        port = env["DATABASE_PORT"]
        database = env["DATABASE_NAME"]
    except KeyError as e:
        print(f"Missing required key in env file: {e}")
        sys.exit(1)

    # Use absolute path for cleaner output
    filename = Path(__file__).parent.resolve() / "alembic.ini.sample"
    print(f"Reading alembic template: {filename}")

    with open(filename, "r") as configfile:
        lines = configfile.readlines()

    new_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    print(f"New connection URL: {new_url}")

    # Check if we found and updated the line
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith("sqlalchemy.url"):
            lines[i] = f"sqlalchemy.url = {new_url}\n"
            updated = True
            break

    if not updated:
        print(f"Warning: Could not find 'sqlalchemy.url' line in {filename}")
        sys.exit(1)

    filename = Path(__file__).parent.resolve() / "alembic.ini"
    with open(filename, "w") as configfile:
        configfile.writelines(lines)

    print("✅ Connection string updated successfully!")
