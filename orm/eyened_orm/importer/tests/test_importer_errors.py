from eyened_orm.importer.importer_dtos import ImportRow
from eyened_orm.importer.importer_errors import (
    direct_missing_lookup_fields,
    missing_parent_error,
)
from eyened_orm.importer.importer_mappings_image import (
    DEVICE_INSTANCE,
    DEVICE_MODEL,
    IMAGE_INSTANCE,
)


def test_direct_missing_lookup_fields():
    row = ImportRow(manufacturer="m")
    assert direct_missing_lookup_fields(DEVICE_MODEL, row) == [
        "manufacturer_model_name"
    ]


def test_missing_parent_error_one_lookup_hop():
    cache = type(
        "Cache",
        (),
        {"get": lambda self, entity, row: None, "lookup_natural": lambda *a: None},
    )()
    row = ImportRow(manufacturer="m", device_description="d")
    err = missing_parent_error(
        cache,
        entity=IMAGE_INSTANCE,
        parent=DEVICE_INSTANCE,
        row=row,
    )
    assert "manufacturer_model_name" in str(err)
    assert "DeviceInstance" in str(err)


def test_missing_parent_error_skips_anonymous_lookup_fields():
    from eyened_orm.importer.importer_mappings_image import SERIES

    class Cache:
        def get(self, entity, row):
            if entity is SERIES:
                return object()
            return None

        def lookup_natural(self, entity, row):
            return None

    row = ImportRow(
        object_key="x.png",
        manufacturer="m",
        device_description="d",
    )
    err = missing_parent_error(
        Cache(),
        entity=type("E", (), {"name": "ImageStorage"})(),
        parent=IMAGE_INSTANCE,
        row=row,
    )
    msg = str(err)
    assert "manufacturer_model_name" in msg
    assert "sop_instance_uid" not in msg
