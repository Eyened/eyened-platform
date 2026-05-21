from __future__ import annotations

from eyened_orm.importer.preparation import infer_storage_format, prepare_rows
from eyened_orm.importer.importer_dtos import ImportRow


def test_infer_storage_format_basic():
    assert infer_storage_format("a.png") == "image/png"
    assert infer_storage_format("a.JPG") == "image/jpeg"
    assert infer_storage_format("a.dcm") == "dicom"
    assert infer_storage_format("a") == "png_series"
    assert infer_storage_format("a.bin") == "binary"


def test_prepare_rows_applies_defaults_and_infers_format():
    defaults = {
        "manufacturer": "test-manufacturer",
        "manufacturer_model_name": "test-model",
        "device_description": "test-description",
    }
    rows = [
        ImportRow(
            project_name="proj",
            storage_backend_key="sb",
            object_key="x.png",
            patient_identifier="p1",
        )
    ]

    prepared = prepare_rows(rows, defaults=defaults, infer_image_format=True)
    assert prepared[0].manufacturer == "test-manufacturer"
    assert prepared[0].manufacturer_model_name == "test-model"
    assert prepared[0].device_description == "test-description"
    assert prepared[0].image_storage_format == "image/png"


def test_prepare_rows_respects_explicit_image_storage_format():
    rows = [
        ImportRow(
            project_name="proj",
            storage_backend_key="sb",
            object_key="x.png",
            patient_identifier="p1",
            image_storage_format="custom",
        )
    ]
    prepared = prepare_rows(rows, infer_image_format=True)
    assert prepared[0].image_storage_format == "custom"

