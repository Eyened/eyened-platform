from datetime import date, datetime

from eyened_orm import (
    Creator,
    DeviceInstance,
    DeviceModel,
    Feature,
    ImageInstance,
    Patient,
    Project,
    Segmentation,
    Series,
    Study,
)
from eyened_orm.project import ExternalEnum
from eyened_orm.segmentation import DataRepresentation, Datatype
from eyened_orm.repositories.segmentation_repository import SegmentationRepository
from eyened_orm.utils.factories import admin_scope


def _make_segmentation(
    session,
    key: str,
    *,
    inactive: bool = False,
    feature_id: int | None = None,
    reference_segmentation_id: int | None = None,
) -> Segmentation:
    """Build the minimal, dimensionally-consistent FK graph a Segmentation
    requires (Project→Patient→Study→Series→Device→ImageInstance + Creator +
    Feature) and return a dense 1x4x4 row matching the image shape."""
    project = Project(ProjectName=f"P-{key}", External=ExternalEnum.N)
    session.add(project)
    session.flush()
    patient = Patient(PatientIdentifier=f"ID-{key}", ProjectID=project.ProjectID)
    session.add(patient)
    session.flush()
    study = Study(PatientID=patient.PatientID, StudyDate=date.today())
    session.add(study)
    session.flush()
    series = Series(StudyID=study.StudyID)
    session.add(series)
    session.flush()
    model = DeviceModel(Manufacturer=f"Mf-{key}", ManufacturerModelName=f"M-{key}")
    session.add(model)
    session.flush()
    device = DeviceInstance(DeviceModelID=model.DeviceModelID, Description="d")
    session.add(device)
    session.flush()
    image = ImageInstance(
        PublicID=f"img-{key}",
        SeriesID=series.SeriesID,
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier=f"ds-{key}",
        Rows_y=4,
        Columns_x=4,
    )
    session.add(image)
    session.flush()
    creator = Creator(CreatorName=f"c-{key}", IsHuman=True)
    session.add(creator)
    session.flush()
    if feature_id is None:
        feature = Feature(FeatureName=f"feat-{key}")
        session.add(feature)
        session.flush()
        feature_id = feature.FeatureID
    seg = Segmentation(
        ImageInstanceID=image.ImageInstanceID,
        FeatureID=feature_id,
        CreatorID=creator.CreatorID,
        DataType=Datatype.R8UI,
        DataRepresentation=DataRepresentation.Binary,
        Depth=1,
        Height=4,
        Width=4,
        ReferenceSegmentationID=reference_segmentation_id,
        Inactive=inactive,
        DateInserted=datetime.now(),
    )
    session.add(seg)
    session.flush()
    return seg


def test_get_with_tag_links_found_and_missing(session):
    """get_with_tag_links returns the row (tag links eager-loaded) or None."""
    seg = _make_segmentation(session, "one")
    repo = SegmentationRepository(session, scope=admin_scope())

    got = repo.get_with_tag_links(seg.SegmentationID)
    assert got is not None and got.SegmentationID == seg.SegmentationID
    assert list(got.SegmentationTagLinks) == []  # eager-loaded, empty

    assert repo.get_with_tag_links(999_999) is None
