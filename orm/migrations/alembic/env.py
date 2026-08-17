from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from eyened_orm import *
from eyened_orm.base import Base
from eyened_orm.config import load_database_settings
from eyened_orm.utils.env import env_flag_enabled, load_env_file
# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# Read before load_env_file() below. That call is load_dotenv(override=True), which
# writes a file's contents into os.environ — so a read placed after it would let any
# .env file switch off the confirmation guard. Read order is the whole protection.
assume_yes = env_flag_enabled(os.environ.get("EYENED_ALEMBIC_ASSUME_YES"))

x_args = context.get_x_argument(as_dictionary=True)
env_file = x_args.get("env_file")
load_env_file(env_file, override=True)
db_settings = load_database_settings()
db_password = db_settings.password.get_secret_value()
db_url = (
    f"mysql+pymysql://{db_settings.user}:{db_password}"
    f"@{db_settings.host}:{db_settings.port}/{db_settings.database}"
)

# if the command alters the database, prompt for confirmation
cmd_opts = getattr(config, "cmd_opts", None)
cmd = getattr(cmd_opts, "cmd", None)
if isinstance(cmd, (list, tuple)):
    cmd = cmd[0] if cmd else None
if callable(cmd):
    cmd = cmd.__name__
no_prompt_cmds = {
    "revision",
    "history",
    "current",
    "heads",
    "branches",
    "show",
    "check",
    "list_templates",
    "stamp",
}
if cmd not in no_prompt_cmds:
    confirm_target = (
        f"{db_settings.user}@{db_settings.host}:{db_settings.port}/{db_settings.database}"
    )
    if assume_yes:
        print(
            f"Target database: {confirm_target}. "
            "Proceeding without confirmation (EYENED_ALEMBIC_ASSUME_YES)."
        )
    else:
        response = input(
            f"Target database: {confirm_target}. Proceed? [y/N] "
        ).strip().lower()
        if response not in {"y", "yes"}:
            print("Aborted by user.")
            sys.exit(1)
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
