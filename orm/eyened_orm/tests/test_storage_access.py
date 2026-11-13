"""resolve_image_data_ref: primary vs storage_id selection."""

from types import SimpleNamespace

import pytest

from eyened_orm.storage_access import resolve_image_data_ref


def _backend(key: str = "data"):
    return SimpleNamespace(Key=key)


def _storage(*, id: int, key: str, fmt: str, primary: bool, backend_key: str = "data"):
    return SimpleNamespace(
        ImageStorageID=id,
        ObjectKey=key,
        Format=fmt,
        IsPrimary=primary,
        StorageBackend=_backend(backend_key),
    )


def _instance(storages, primary=None):
    primary = primary or next(s for s in storages if s.IsPrimary)
    return SimpleNamespace(
        ImageStorages=storages,
        primary_storage=primary,
    )


def test_default_uses_primary_storage():
    storages = [
        _storage(id=1, key="struct.dcm", fmt="dicom", primary=True),
        _storage(id=2, key="flow.dcm", fmt="angio_flow", primary=False),
    ]
    ref = resolve_image_data_ref(_instance(storages))
    assert ref.backend_key == "data"
    assert ref.relative_path == "struct.dcm"


def test_storage_id_selects_angio_flow():
    storages = [
        _storage(id=1, key="struct.dcm", fmt="dicom", primary=True),
        _storage(id=2, key="flow.dcm", fmt="angio_flow", primary=False),
    ]
    ref = resolve_image_data_ref(_instance(storages), storage_id=2)
    assert ref.relative_path == "flow.dcm"


def test_unknown_storage_id_raises():
    storages = [
        _storage(id=1, key="struct.dcm", fmt="dicom", primary=True),
    ]
    with pytest.raises(ValueError, match="not found"):
        resolve_image_data_ref(_instance(storages), storage_id=99)


def test_angio_flow_is_whole_object_like_dicom():
    storage = _storage(id=2, key="flow.dcm", fmt="angio_flow", primary=True)
    ref = resolve_image_data_ref(_instance([storage]), meta=True)
    assert ref.relative_path == "flow.dcm"
