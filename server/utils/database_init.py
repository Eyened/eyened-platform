from eyened_orm import AnnotationType

import os
import warnings
from eyened_orm.db import create_connection_string_mysql
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from eyened_orm.Creator import Creator
from eyened_orm.base import Base

from ..db import config, DBManager
from ..routes.utils import password_hash

def create_database():
    # create generic engine for database creation
    temp_engine = create_engine(create_connection_string_mysql(**{**config["database"], 'database': None}))
    
    # Create database if it doesn't exist
    dbname = config["database"]["database"]
    with temp_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {dbname}"))

    # Now create tables using normal engine
    engine = DBManager.get_engine()
    Base.metadata.create_all(engine)

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

    if admin_username == "admin" and admin_password == "admin":
        raise ValueError("ADMIN_USERNAME and ADMIN_PASSWORD must be changed from default values")
    
    # Check if admin already exists
    existing_admin = session.query(Creator).filter(
        Creator.CreatorName == admin_username
    ).first()

    print(f"Admin user: {admin_username}")
    print(f"Admin password: {admin_password}")
    if existing_admin:
        warnings.warn("Admin user already exists, skipping creation")
        return

    
    # Create new admin user
    new_admin = Creator()
    new_admin.CreatorName = admin_username
    new_admin.Password = password_hash(admin_password)
    new_admin.IsHuman = True
    new_admin.Description = "Default admin user created during initialization"
    
    session.add(new_admin)
    session.commit()


def init_annotation_types(session):
    types = (
        'Segmentation 2D',
        'Segmentation OCT B-scan',
        'Segmentation OCT Enface',
        'Segmentation OCT Volume'
    )
    interpretations = (
        'Binary mask',
        'Probability',
        'R/G mask',
        'Label numbers',
        'Layer bits'
    )
    additional_types = [
        ('Segmentation 2D masked', 'R/G mask')
    ]

    index = {
        (a.AnnotationTypeName, a.Interpretation): a
        for a in AnnotationType.fetch_all(session)
    }
    expected = [
        (name, interpretation)
        for name in types
        for interpretation in interpretations
    ] + additional_types
    
    for name, interpretation in expected:
        if (name, interpretation) not in index:
            annotation_type = AnnotationType(
                AnnotationTypeName=name,
                Interpretation=interpretation
            )
            print('Adding annotation type:', name, interpretation)
            session.add(annotation_type)
    session.commit()
