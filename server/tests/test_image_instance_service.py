import datetime

import pytest

from eyened_orm import (
    DeviceInstance,
    DeviceModel,
    ImageInstance,
    Patient,
    Project,
    Series,
    Study,
)
from eyened_orm.project import ExternalEnum
from eyened_orm.repositories.image_instance_repository import ImageInstanceRepository
from eyened_orm.repositories.tag_repository import TagRepository

from server.services.exceptions import NotFoundError
from server.services.image_instance_service import ImageInstanceService


class FakeAuditLogger:
    """Records logging calls without touching the filesystem (no mock lib)."""

    def __init__(self) -> None:
        self.inserts: list[dict] = []
        self.updates: list[dict] = []
        self.deletes: list[dict] = []

    def log_insert(self, **kwargs) -> None:
        self.inserts.append(kwargs)

    def log_update(self, **kwargs) -> None:
        self.updates.append(kwargs)

    def log_delete(self, **kwargs) -> None:
        self.deletes.append(kwargs)


def _make_image(session, public_id: str) -> int:
    """Build the minimal graph an ImageInstance FK-requires; return its id."""
    project = Project(ProjectName=f"P-{public_id}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"ID-{public_id}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=datetime.date(2020, 1, 1))
    session.add(study)
    session.flush()
    series = Series(StudyID=study.StudyID)
    session.add(series)
    session.flush()
    model = DeviceModel(Manufacturer=f"Mf-{public_id}", ManufacturerModelName=f"M-{public_id}")
    session.add(model)
    session.flush()
    device = DeviceInstance(DeviceModelID=model.DeviceModelID, Description="d")
    session.add(device)
    session.flush()
    image = ImageInstance(
        PublicID=public_id,
        SeriesID=series.SeriesID,
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier=f"ds-{public_id}",
    )
    session.add(image)
    session.flush()
    return image.ImageInstanceID


def _service(logger=None) -> ImageInstanceService:
    return ImageInstanceService(
        ImageInstanceRepository(), TagRepository(), logger=logger
    )


_READ_KW = dict(
    with_segmentations=False,
    with_form_annotations=False,
    with_model_segmentations=False,
)


def test_get_instance_returns_it(session):
    """get_instance returns the instance at the given id."""
    image_id = _make_image(session, "pub-1")
    session.commit()

    got = _service().get_instance(session, image_id, **_READ_KW)

    assert got.ImageInstanceID == image_id


def test_get_instance_unknown_raises_not_found(session):
    """Getting a missing instance is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_instance(session, 999_999, **_READ_KW)


def test_get_by_public_id_unknown_raises_not_found(session):
    """Resolving a missing PublicID is translated to NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_by_public_id(session, "nope", **_READ_KW)


def test_get_for_storage_unknown_raises_not_found(session):
    """get_for_storage on a missing PublicID raises NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        _service().get_for_storage(session, "missing")
