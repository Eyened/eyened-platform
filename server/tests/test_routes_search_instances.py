from datetime import date, datetime

from eyened_orm import (
    DeviceInstance,
    DeviceModel,
    ImageInstance,
    ImageStorage,
    Patient,
    Project,
    Series,
    StorageBackend,
    Study,
)
from eyened_orm.project import ExternalEnum


def test_instance_search_returns_a_seeded_instance(client, session):
    """The harness reaches the real endpoint and renders one seeded instance."""
    backend = StorageBackend(Key="bk", Kind="local")
    session.add(backend)
    session.flush()
    project = Project(ProjectName="P", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier="ID", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=date(2024, 1, 1))
    session.add(study)
    session.flush()
    series = Series(StudyID=study.StudyID)
    session.add(series)
    session.flush()
    model = DeviceModel(Manufacturer="Mf", ManufacturerModelName="M")
    session.add(model)
    session.flush()
    device = DeviceInstance(DeviceModelID=model.DeviceModelID, Description="d")
    session.add(device)
    session.flush()
    image = ImageInstance(
        PublicID="img-a",
        SeriesID=series.SeriesID,
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier="ds-a",
        Rows_y=4,
        Columns_x=4,
        DateInserted=datetime(2024, 1, 1),
    )
    session.add(image)
    session.flush()
    session.add(
        ImageStorage(
            ImageInstanceID=image.ImageInstanceID,
            StorageBackendID=backend.StorageBackendID,
            ObjectKey="obj-a",
            Format="png",
            IsPrimary=True,
        )
    )
    session.commit()

    resp = client.post(
        "/instances/search",
        json={"conditions": [], "order_by": "Study Date", "order": "ASC", "include_count": True},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["result_ids"] == ["img-a"]
    assert body["count"] == 1
