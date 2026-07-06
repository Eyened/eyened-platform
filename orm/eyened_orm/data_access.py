from __future__ import annotations

import io
import json
import os
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np

from eyened_orm.api_client import get_api_client
from eyened_orm.segmentation_storage import (
    read_segmentation_data as read_segmentation_data_local,
    write_segmentation_data as write_segmentation_data_local,
)
from eyened_orm.storage_access import (
    resolve_image_data_ref,
    resolve_thumbnail_ref,
)


class DataAccessAdapter(ABC):
    @abstractmethod
    def image_path(self, image_instance) -> Path:
        raise NotImplementedError

    @abstractmethod
    def read_image_data(
        self,
        image_instance,
        *,
        index: Optional[int] = None,
        meta: bool = False,
    ) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def read_thumbnail(self, image_instance, *, size: int) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def read_segmentation_data(
        self, segmentation, *, axis: Optional[int] = None, slice_index: Optional[int] = None
    ) -> Optional[np.ndarray]:
        raise NotImplementedError

    @abstractmethod
    def write_segmentation_data(
        self,
        segmentation,
        data: np.ndarray,
        *,
        axis: Optional[int] = None,
        slice_index: Optional[int] = None,
    ) -> int:
        raise NotImplementedError


def is_local_storage_enabled() -> bool:
    # local mode requires backend-key mount mapping for image storages
    return bool(os.getenv("EYENED_STORAGE_MOUNTS", "").strip())


@lru_cache(maxsize=1)
def load_storage_mounts() -> dict[str, Path]:
    raw = os.getenv("EYENED_STORAGE_MOUNTS", "").strip()
    if not raw:
        return {}

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("EYENED_STORAGE_MOUNTS must be a JSON object")
    return {str(k): Path(str(v)) for k, v in parsed.items()}


@lru_cache(maxsize=1)
def load_storage_root() -> Path:
    raw = os.getenv("EYENED_STORAGE_ROOT", "").strip()
    if raw:
        return Path(raw)
    return Path("/storage")


class LocalDataAccessAdapter(DataAccessAdapter):
    def image_path(self, image_instance) -> Path:
        mounts = load_storage_mounts()
        ref = resolve_image_data_ref(image_instance)
        return ref.local_path(mounts)

    def read_image_data(
        self,
        image_instance,
        *,
        index: Optional[int] = None,
        meta: bool = False,
    ) -> bytes:
        mounts = load_storage_mounts()
        ref = resolve_image_data_ref(image_instance, index=index, meta=meta)
        return ref.local_path(mounts).read_bytes()

    def read_thumbnail(self, image_instance, *, size: int) -> bytes:
        ref = resolve_thumbnail_ref(image_instance, size=size)
        thumb_path = load_storage_root() / "thumbnails" / ref.relative_path
        return thumb_path.read_bytes()

    def read_segmentation_data(
        self, segmentation, *, axis: Optional[int] = None, slice_index: Optional[int] = None
    ) -> Optional[np.ndarray]:
        return read_segmentation_data_local(
            segmentation, axis=axis, slice_index=slice_index
        )

    def write_segmentation_data(
        self,
        segmentation,
        data: np.ndarray,
        *,
        axis: Optional[int] = None,
        slice_index: Optional[int] = None,
    ) -> int:
        return write_segmentation_data_local(
            segmentation, data, axis=axis, slice_index=slice_index
        )


class ApiDataAccessAdapter(DataAccessAdapter):
    def image_path(self, image_instance) -> Path:
        storage = image_instance.primary_storage
        if storage and storage.StorageBackend and storage.StorageBackend.Key:
            return Path("/") / storage.StorageBackend.Key / image_instance.object_key
        return Path(image_instance.object_key)

    def read_image_data(
        self,
        image_instance,
        *,
        index: Optional[int] = None,
        meta: bool = False,
    ) -> bytes:
        params = {}
        if index is not None:
            params["index"] = index
        if meta:
            params["meta"] = True
        client = get_api_client()
        resp = client.get(image_instance.data_endpoint, params=params or None)
        resp.raise_for_status()
        return resp.content

    def read_thumbnail(self, image_instance, *, size: int) -> bytes:
        client = get_api_client()
        resp = client.get(
            f"/api/images/{image_instance.PublicID}/thumbnail", params={"size": size}
        )
        resp.raise_for_status()
        return resp.content

    def read_segmentation_data(
        self, segmentation, *, axis: Optional[int] = None, slice_index: Optional[int] = None
    ) -> Optional[np.ndarray]:
        if segmentation.ZarrArrayIndex is None:
            return None
        params = None
        if axis is not None or slice_index is not None:
            params = {"axis": axis, "scan_nr": slice_index}

        client = get_api_client()
        resp = client.get(segmentation._api_data_path(), params=params)
        if resp.status_code == 204:
            return None
        resp.raise_for_status()
        return np.load(io.BytesIO(resp.content), allow_pickle=False)

    def write_segmentation_data(
        self,
        segmentation,
        data: np.ndarray,
        *,
        axis: Optional[int] = None,
        slice_index: Optional[int] = None,
    ) -> int:
        params = None
        if axis is not None or slice_index is not None:
            params = {"axis": axis, "scan_nr": slice_index}

        np_buf = io.BytesIO()
        np.save(np_buf, data)
        payload = np_buf.getvalue()

        client = get_api_client()
        resp = client.put(
            segmentation._api_data_path(),
            params=params,
            headers={"Content-Type": "application/octet-stream"},
            data=payload,
        )
        resp.raise_for_status()

        zarr_index = segmentation.ZarrArrayIndex
        try:
            body = resp.json()
            if isinstance(body, dict):
                if "ZarrArrayIndex" in body:
                    zarr_index = body["ZarrArrayIndex"]
                elif "zarr_array_index" in body:
                    zarr_index = body["zarr_array_index"]
        except ValueError:
            pass

        if (
            segmentation.ScanIndices is not None
            and segmentation.is_sparse
            and axis == segmentation.SparseAxis
        ):
            if slice_index not in segmentation.ScanIndices:
                scan_indices = segmentation.ScanIndices.copy()
                scan_indices.append(slice_index)
                segmentation.ScanIndices = scan_indices

        segmentation.ZarrArrayIndex = zarr_index
        return zarr_index


@lru_cache(maxsize=1)
def get_data_access_adapter() -> DataAccessAdapter:
    if is_local_storage_enabled():
        print("Using local storage")
        return LocalDataAccessAdapter()
    print("Using API storage")
    return ApiDataAccessAdapter()
