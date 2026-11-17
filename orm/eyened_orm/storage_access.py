from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageRef:
    backend_key: str
    relative_path: str

    @property
    def nginx_path(self) -> str:
        return f"/{self.backend_key}/{self.relative_path}"

    def local_path(self, mounts: dict[str, Path]) -> Path:
        root = mounts.get(self.backend_key)
        if root is None:
            raise KeyError(
                f"Storage backend '{self.backend_key}' is not configured in EYENED_STORAGE_MOUNTS"
            )
        return root / self.relative_path


def _storage_for_ref(image_instance, storage_id: int | None):
    if storage_id is None:
        storage = image_instance.primary_storage
        if not storage:
            raise ValueError("Primary image storage not found")
        return storage

    for storage in getattr(image_instance, "ImageStorages", None) or []:
        if storage.ImageStorageID == storage_id:
            return storage
    raise ValueError(f"Image storage {storage_id} not found on this instance")


def resolve_image_data_ref(
    image_instance,
    *,
    index: int | None = 0,
    meta: bool = False,
    storage_id: int | None = None,
) -> StorageRef:
    storage = _storage_for_ref(image_instance, storage_id)
    if not storage.StorageBackend or not storage.StorageBackend.Key:
        raise ValueError("Image storage has no storage backend")
    if not storage.ObjectKey:
        raise ValueError("Image storage has no ObjectKey")

    key = storage.StorageBackend.Key
    obj = storage.ObjectKey
    fmt = storage.Format

    if fmt == "png_series":
        path, source_id = obj.rsplit("/", 1)
        if meta:
            return StorageRef(key, f"{path}/metadata.json")
        if index is None:
            raise ValueError(
                "Index is required for png_series format if not fetching metadata"
            )
        return StorageRef(key, f"{path}/{source_id}_{index}.png")

    if fmt == "binary":
        suffix = ".json" if meta else ".binary"
        return StorageRef(key, f"{obj}{suffix}")

    if fmt == "mhd":
        return StorageRef(key, obj if meta else f"{obj[:-4]}.raw")

    # Whole-object formats: dicom, image/png, image/jpeg, and any other
    # Format that is a single file.
    return StorageRef(key, obj)


def resolve_thumbnail_ref(image_instance, *, size: int = 144) -> StorageRef:
    if not image_instance.ThumbnailPath:
        raise ValueError("Image thumbnail path is missing")
    from eyened_orm.importer.thumbnails import thumbnail_filename

    return StorageRef(
        "thumbnails",
        thumbnail_filename(image_instance.ThumbnailPath, size),
    )
