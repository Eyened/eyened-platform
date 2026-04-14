from datetime import datetime

import pytest

from eyened_orm import Database, Base
from eyened_orm.importer.importer_dtos import PatientImport, ImageImport, SeriesImport, StudyImport
from eyened_orm.importer.importer import Importer
from eyened_orm.utils.config import load_config, EyenedORMConfig

# TODO: move to common conftest file
@pytest.fixture(scope="session")
def config():
    config_dict = {
        "database": {"host": "localhost", "port": "3306", "user": "eyened", "password": "eyened", "database": "eyened_database",},
        "secret_key": "secret",
        "images_basepath": "",
        "segmentations_zarr_store": "",
        "thumbnails_path": "",
        "annotations_path": "",
        "default_study_date": None,
        "image_server_url": "",
    }
    return load_config(config_dict)

# TODO: move to common conftest file
@pytest.fixture
def db_session(config: EyenedORMConfig):
    """Set up a database session for testing (using the mysql database from the dev docker setup)"""
    db = Database(config)
    Base.metadata.create_all(db.engine)

    session = db.create_session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_importer_reuse_existing_series(db_session, config):
    """When importing a user twice, there should not be a conflict already existing series data"""
    # Regression test, ref: https://github.com/Eyened/eyened-platform/issues/100

    # Create a minimal patient: 1 image, 1 series, 1 study, 1 patient, 1 project
    image = ImageImport(
        image = "/tmp/image-1.dcm",
        sop_instance_uid=f"image-1",
    )
    # Setting the SeriesImport.series_instance_uid here is the crux
    series = SeriesImport(images=[image], series_number=1, series_instance_uid="series-1")
    study = StudyImport(series=[series], study_date=datetime.now().date())
    patient = PatientImport(studies=[study], patient_identifier="patient-1", project_name="project-1")
    import_data = [patient]

    # Set up the importer and run it.
    importer = Importer(session=db_session, config=config, create_projects=True, create_patients=True, create_studies=True,
                        create_series=True, generate_thumbnails=False, )
    importer.import_many(import_data, summary=False)
    del importer

    # Now import again
    importer_2 = Importer(session=db_session, create_projects=True, create_patients=True, create_studies=True,
                          create_series=True, generate_thumbnails=False, )
    importer_2.import_many(import_data, summary=False)
