from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

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
from eyened_orm.importer.importer import plan_import
from eyened_orm.importer.importer_dtos import ImportRow


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_import_project_only_then_update_description(session):
    defaults = {
        "project_external": "Y",
        "project_description": "initial project description",
    }

    run1 = plan_import(
        session,
        [ImportRow(project_name="proj-only")],
        defaults=defaults,
    )
    run1.apply()
    session.commit()

    assert _count(session, Project) == 1
    assert _count(session, Patient) == 0
    assert _count(session, Study) == 0
    assert _count(session, Series) == 0
    assert _count(session, ImageInstance) == 0
    assert _count(session, ImageStorage) == 0

    proj = Project.by_name(session, "proj-only")
    assert proj is not None
    assert proj.Description == "initial project description"

    run2 = plan_import(
        session,
        [
            ImportRow(
                project_name="proj-only",
                project_description="updated project description",
            )
        ],
        defaults=defaults,
    )
    run2.apply()
    session.commit()

    proj2 = Project.by_name(session, "proj-only")
    assert proj2 is not None
    assert proj2.Description == "updated project description"


def test_import_project_and_patient_only_then_update_patient_fields(session):
    defaults = {
        "project_external": "Y",
    }
    run1 = plan_import(
        session,
        [
            ImportRow(
                project_name="proj-pp",
                patient_identifier="pat-1",
            )
        ],
        defaults=defaults,
    )
    run1.apply()
    session.commit()

    assert _count(session, Project) == 1
    assert _count(session, Patient) == 1
    assert _count(session, Study) == 0
    assert _count(session, Series) == 0
    assert _count(session, ImageInstance) == 0
    assert _count(session, ImageStorage) == 0

    # Second pass: update just project/patient-level fields (no study/image keys).
    run2 = plan_import(
        session,
        [
            ImportRow(
                project_name="proj-pp",
                patient_identifier="pat-1",
                project_description="proj updated",
            )
        ],
        defaults=defaults,
    )
    run2.apply()
    session.commit()

    proj = Project.by_name(session, "proj-pp")
    assert proj is not None
    assert proj.Description == "proj updated"


def test_import_device_only_then_update_serial_number(session):
    defaults = {}

    run1 = plan_import(
        session,
        [
            ImportRow(
                manufacturer="mfr",
                manufacturer_model_name="model",
                device_description="dev-1",
                device_serial_number="SERIAL-A",
            )
        ],
        defaults=defaults,
    )
    run1.apply()
    session.commit()

    assert _count(session, DeviceModel) == 1
    assert _count(session, DeviceInstance) == 1
    assert _count(session, Project) == 0
    assert _count(session, Patient) == 0
    assert _count(session, ImageInstance) == 0

    dev = session.scalar(select(DeviceInstance))
    assert dev is not None
    assert dev.SerialNumber == "SERIAL-A"

    run2 = plan_import(
        session,
        [
            ImportRow(
                manufacturer="mfr",
                manufacturer_model_name="model",
                device_description="dev-1",
                device_serial_number="SERIAL-B",
            )
        ],
        defaults=defaults,
    )
    run2.apply()
    session.commit()

    dev2 = session.scalar(select(DeviceInstance))
    assert dev2 is not None
    assert dev2.SerialNumber == "SERIAL-B"


def test_import_image_then_update_modality(session):
    defaults = {
        "project_external": "Y",
        "manufacturer": "mfr",
        "manufacturer_model_name": "model",
        "device_description": "dev",
        "dataset_identifier": "",
        "storage_backend_kind": "kind",
    }
    d = date(2026, 4, 15)

    run1 = plan_import(
        session,
        [
            ImportRow(
                project_name="proj-img",
                patient_identifier="pat",
                study_date=d,
                series_instance_uid="SER-1",
                sop_instance_uid="SOP-1",
                storage_backend_key="sb-1",
                object_key="img-1.png",
                modality="ColorFundus",
                laterality="L",
            )
        ],
        defaults=defaults,
    )
    run1.apply()
    session.commit()

    img1 = ImageInstance.by_column(session, SOPInstanceUid="SOP-1")
    assert img1 is not None
    assert getattr(img1.Modality, "value", img1.Modality) == "ColorFundus"

    run2 = plan_import(
        session,
        [
            ImportRow(
                project_name="proj-img",
                patient_identifier="pat",
                study_date=d,
                series_instance_uid="SER-1",
                sop_instance_uid="SOP-1",
                storage_backend_key="sb-1",
                object_key="img-1.png",
                modality="OCT",  # change a specific field
                laterality="L",
            )
        ],
        defaults=defaults,
    )
    run2.apply()
    session.commit()

    img2 = ImageInstance.by_column(session, SOPInstanceUid="SOP-1")
    assert img2 is not None
    assert getattr(img2.Modality, "value", img2.Modality) == "OCT"


def test_import_image_then_update_device_fk(session):
    defaults = {
        "project_external": "Y",
        "manufacturer": "mfr",
        "manufacturer_model_name": "model",
        "dataset_identifier": "",
        "storage_backend_kind": "kind",
    }
    d = date(2026, 4, 15)

    run1 = plan_import(
        session,
        [
            ImportRow(
                project_name="proj-fk",
                patient_identifier="pat",
                study_date=d,
                series_instance_uid="SER-1",
                sop_instance_uid="SOP-1",
                storage_backend_key="sb-1",
                object_key="img-1.png",
                modality="ColorFundus",
                laterality="L",
                device_description="dev-A",
                device_serial_number="SERIAL-A",
            )
        ],
        defaults=defaults,
    )
    run1.apply()
    session.commit()

    img1 = ImageInstance.by_column(session, SOPInstanceUid="SOP-1")
    assert img1 is not None
    assert img1.DeviceInstance is not None
    assert img1.DeviceInstance.Description == "dev-A"

    # Second pass: same image, but now updating the devicedescription
    # Lookup key changes, but device instance should be reused rather than created again
    run2 = plan_import(
        session,
        [
            ImportRow(
                project_name="proj-fk",
                patient_identifier="pat",
                study_date=d,
                series_instance_uid="SER-1",
                sop_instance_uid="SOP-1",
                storage_backend_key="sb-1",
                object_key="img-1.png",
                modality="ColorFundus",
                laterality="L",
                device_description="dev-B",
                device_serial_number="SERIAL-B",
            )
        ],
        defaults=defaults,
    )
    run2.apply()
    session.commit()

    assert _count(session, DeviceInstance) == 1  # same device instance is reused
    img2 = ImageInstance.by_column(session, SOPInstanceUid="SOP-1")
    assert img2 is not None
    assert img2.DeviceInstance is not None
    assert img2.DeviceInstance.Description == "dev-B"


def test_image_instance_can_be_looked_up_by_sop_uid_public_id_or_pk(session):
    defaults = {
        "project_external": "Y",
        "manufacturer": "mfr",
        "manufacturer_model_name": "model",
        "device_description": "dev",
        "dataset_identifier": "",
        "storage_backend_kind": "kind",
    }
    d = date(2026, 4, 15)

    run1 = plan_import(
        session,
        [
            ImportRow(
                project_name="proj-img-keys",
                patient_identifier="pat",
                study_date=d,
                series_instance_uid="SER-1",
                sop_instance_uid="SOP-1",
                storage_backend_key="sb-1",
                object_key="img-1.png",
                modality="ColorFundus",
                laterality="L",
            )
        ],
        defaults=defaults,
    )
    run1.apply()
    session.commit()

    img1 = ImageInstance.by_column(session, SOPInstanceUid="SOP-1")
    assert img1 is not None

    image_instance_id = img1.ImageInstanceID
    public_id = img1.PublicID

    run2 = plan_import(
        session,
        [
            ImportRow(
                public_id=public_id,
                modality="OCT",
                laterality="R",
            ),
        ],
        defaults=defaults,
    )
    run2.apply()
    session.commit()

    assert _count(session, ImageInstance) == 1

    img2 = session.scalar(select(ImageInstance))
    assert img2 is not None
    assert img2.ImageInstanceID == image_instance_id
    assert img2.PublicID == public_id
    assert img2.SOPInstanceUid == "SOP-1"
    assert img2.Modality.value == "OCT"
    assert img2.Laterality.value == "R"


def test_import_image_public_id_cannot_be_changed(session):
    defaults = {
        "project_external": "Y",
        "manufacturer": "mfr",
        "manufacturer_model_name": "model",
        "device_description": "dev",
        "dataset_identifier": "",
        "storage_backend_kind": "kind",
    }
    d = date(2026, 4, 15)

    run1 = plan_import(
        session,
        [
            ImportRow(
                project_name="proj-public-id",
                patient_identifier="pat",
                study_date=d,
                series_instance_uid="SER-1",
                sop_instance_uid="SOP-1",
                storage_backend_key="sb-1",
                object_key="img-1.png",
                modality="ColorFundus",
                laterality="L",
            )
        ],
        defaults=defaults,
    )
    run1.apply()
    session.commit()

    img1 = ImageInstance.by_column(session, SOPInstanceUid="SOP-1")
    assert img1 is not None
    public_id = img1.PublicID

    run2 = plan_import(
        session,
        [
            ImportRow(
                image_instance_id=img1.ImageInstanceID,
                public_id="cannot_be_changed",
                laterality="R",
            )
        ],
        defaults=defaults,
    )
    run2.apply()
    session.commit()

    img2 = session.scalar(
        select(ImageInstance).where(ImageInstance.ImageInstanceID == img1.ImageInstanceID)
    )
    assert img2 is not None
    assert img2.PublicID == public_id
    assert img2.Laterality.value == "R"


def test_import_image_lookup_by_pk_can_edit_sop_instance_uid(session):
    defaults = {
        "project_external": "Y",
        "manufacturer": "mfr",
        "manufacturer_model_name": "model",
        "device_description": "dev",
        "dataset_identifier": "",
        "storage_backend_kind": "kind",
    }
    d = date(2026, 4, 15)

    run1 = plan_import(
        session,
        [
            ImportRow(
                project_name="proj-sop-pk",
                patient_identifier="pat",
                study_date=d,
                series_instance_uid="SER-1",
                sop_instance_uid="SOP-OLD",
                storage_backend_key="sb-1",
                object_key="img-1.png",
                modality="ColorFundus",
                laterality="L",
            )
        ],
        defaults=defaults,
    )
    run1.apply()
    session.commit()

    img1 = ImageInstance.by_column(session, SOPInstanceUid="SOP-OLD")
    assert img1 is not None

    run2 = plan_import(
        session,
        [
            ImportRow(
                image_instance_id=img1.ImageInstanceID,
                sop_instance_uid="SOP-NEW",
            )
        ],
        defaults=defaults,
    )
    run2.apply()
    session.commit()

    assert ImageInstance.by_column(session, SOPInstanceUid="SOP-OLD") is None

    img2 = ImageInstance.by_column(session, SOPInstanceUid="SOP-NEW")
    assert img2 is not None
    assert img2.ImageInstanceID == img1.ImageInstanceID

