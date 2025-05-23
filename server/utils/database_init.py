from eyened_orm import AnnotationType
from types import SimpleNamespace

import os
import warnings
from eyened_orm.db import create_connection_string
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from eyened_orm import Creator, SourceInfo, ModalityTable
from eyened_orm.base import Base

from ..db import settings, DBManager
from ..routes.auth import create_user



def create_database():
    # create generic engine for database creation
    root_config = SimpleNamespace(
        user="root",
        password=os.environ.get("DB_ROOT_PASSWORD"),
        host=settings.database.host,
        port=settings.database.port,
        database=None  # Don't specify database initially
    )
    
    temp_engine = create_engine(create_connection_string(root_config))

    # First check if database exists
    try:
        with temp_engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{settings.database.database}'"
                )
            )
            if not result.fetchone():
                # Database doesn't exist, try to create it
                try:
                    conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {settings.database.database}"))
                except Exception as e:
                    raise RuntimeError(
                        f"Database {settings.database.database} does not exist and could not be created. Error: {str(e)}"
                    )
    except Exception as e:
        raise RuntimeError(
            f"Could not check if database {settings.database.database} exists. Error: {str(e)}"
        )

    # Create user if it doesn't exist
    try:
        create_database_user(temp_engine)
    except Exception as e:
        raise RuntimeError(
            f"Could not create database user for {settings.database.database}. Error: {str(e)}"
        )
    # Now create tables using the correct database
    root_config.database = settings.database.database
    temp_engine = create_engine(create_connection_string(root_config))
    Base.metadata.create_all(temp_engine)


def create_database_user(engine):
    """
    Creates a database user with INSERT, UPDATE, DELETE privileges if it doesn't exist.
    Uses credentials from settings.database.
    """
    db_user = settings.database.user
    db_password = settings.database.password
    db_database = settings.database.database

    try:
        with engine.connect() as conn:
            # Check if user exists
            result = conn.execute(
                text(
                    f"SELECT User FROM mysql.user WHERE User = '{db_user}'"
                )
            )
            if result.fetchone():
                print(f"Database user {db_user} already exists")
            else:
                # Create user if it doesn't exist
                try:
                    conn.execute(text(f"CREATE USER '{db_user}'@'%' IDENTIFIED BY '{db_password}'"))
                    print(f"Created database user: {db_user}")
                except Exception as e:
                    raise RuntimeError(
                        f"Could not create database user {db_user}. Error: {str(e)}"
                    )

            # Grant limited privileges to user
            try:
                conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {db_database}.* TO '{db_user}'@'%'"))
                conn.execute(text("FLUSH PRIVILEGES"))
                print(f"Granted SELECT, INSERT, UPDATE, DELETE privileges to user {db_user} on database {db_database}")
            except Exception as e:
                raise RuntimeError(
                    f"Could not grant privileges to user {db_user}. Error: {str(e)}"
                )

    except Exception as e:
        raise RuntimeError(
            f"Could not manage database user {db_user}. Error: {str(e)}"
        )



def init_admin(session: Session) -> None:
    """
    Initialize an admin user if ADMIN_USERNAME environment variable is set.

    Args:
        session: SQLAlchemy session to use for database operations
    """
    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if admin_username is None or admin_password is None:
        raise ValueError("ADMIN_USERNAME and ADMIN_PASSWORD must be set")

    # Check if admin already exists
    existing_admin = (
        session.query(Creator).filter(Creator.CreatorName == admin_username).first()
    )

    if existing_admin:
        print("Admin user already exists, skipping creation")
        return

    try:
        create_user(
            session=session,
            username=admin_username,
            password=admin_password,
            description="Default admin user created during initialization"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to create admin user: {str(e)}")


def init_other_objects(session):
    # add SourceInfo 37 and Modality 14 if they don't exist
    source_info = session.get(SourceInfo, 37)
    if source_info is None:
        source_info = SourceInfo(
            SourceInfoID=37, SourceName="Default", SourcePath="", ThumbnailPath=""
        )
        session.add(source_info)

    modality = session.get(ModalityTable, 14)
    if modality is None:
        modality = ModalityTable(ModalityID=14, ModalityTag="Default")
        session.add(modality)

    session.commit()


def init_annotation_types(session):
    types = (
        "Segmentation 2D",
        "Segmentation OCT B-scan",
        "Segmentation OCT Enface",
        "Segmentation OCT Volume",
    )
    interpretations = (
        "Binary mask",
        "Probability",
        "R/G mask",
        "Label numbers",
        "Layer bits",
    )
    additional_types = [("Segmentation 2D masked", "R/G mask")]

    index = {
        (a.AnnotationTypeName, a.Interpretation): a
        for a in AnnotationType.fetch_all(session)
    }
    expected = [
        (name, interpretation) for name in types for interpretation in interpretations
    ] + additional_types

    for name, interpretation in expected:
        if (name, interpretation) not in index:
            annotation_type = AnnotationType(
                AnnotationTypeName=name, Interpretation=interpretation
            )
            print("Adding annotation type:", name, interpretation)
            session.add(annotation_type)
    session.commit()
