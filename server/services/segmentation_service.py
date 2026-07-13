from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from eyened_orm import ImageInstance, ModelSegmentation, Segmentation
from eyened_orm.segmentation import DataRepresentation, Datatype
from eyened_orm.tag import SegmentationTagLink, TagType
from eyened_orm.repositories.image_instance_repository import (
    ImageInstanceRepository,
)
from eyened_orm.repositories.segmentation_repository import (
    ModelSegmentationRepository,
    SegmentationRepository,
)
from eyened_orm.repositories.tag_repository import TagRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .acting_user import ActingUser
from .exceptions import BadRequestError, NotFoundError
from .segmentation_data_store import (
    SegmentationDataStore,
    get_segmentation_data_store,
)


class SegmentationService:
    """Business logic for Segmentation CRUD, binary data, and Tag links."""

    def __init__(
        self,
        repository: SegmentationRepository,
        image_repository: ImageInstanceRepository,
        tag_repository: TagRepository,
        data_store: SegmentationDataStore,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.images = image_repository
        self.tags = tag_repository
        self.store = data_store
        self.logger = logger

    def get_segmentation(
        self, session: Session, segmentation_id: int
    ) -> Segmentation:
        """Return a segmentation by id (tag links loaded).

        Raises:
            NotFoundError: If the segmentation does not exist.
        """
        item = self.repository.get_with_tag_links(session, segmentation_id)
        if item is None:
            raise NotFoundError("Segmentation not found")
        return item

    def read_data(
        self,
        session: Session,
        segmentation_id: int,
        *,
        axis: Optional[int] = None,
        scan_nr: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        """Return the stored array for a segmentation (None if none stored).

        Raises:
            NotFoundError: If the segmentation does not exist.
            BadRequestError: If the store rejects the read parameters.
        """
        segmentation = self.repository.get_by_id(session, segmentation_id)
        if segmentation is None:
            raise NotFoundError("Segmentation data not found")
        try:
            return self.store.read(segmentation, axis=axis, slice_index=scan_nr)
        except ValueError as e:
            raise BadRequestError(str(e)) from e


class ModelSegmentationService:
    """Business logic for ModelSegmentation binary data endpoints."""

    def __init__(
        self,
        repository: ModelSegmentationRepository,
        data_store: SegmentationDataStore,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.store = data_store
        self.logger = logger

    def read_data(
        self,
        session: Session,
        model_segmentation_id: int,
        *,
        axis: Optional[int] = None,
        scan_nr: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        """Return the stored array for a model segmentation (None if none).

        Raises:
            NotFoundError: If the model segmentation does not exist.
            BadRequestError: If the store rejects the read parameters.
        """
        item = self.repository.get_by_id(session, model_segmentation_id)
        if item is None:
            raise NotFoundError("ModelSegmentation data not found")
        try:
            return self.store.read(item, axis=axis, slice_index=scan_nr)
        except ValueError as e:
            raise BadRequestError(str(e)) from e


def get_segmentation_service() -> SegmentationService:
    """Default SegmentationService wiring for FastAPI ``Depends()``."""
    return SegmentationService(
        SegmentationRepository(),
        ImageInstanceRepository(),
        TagRepository(),
        get_segmentation_data_store(),
        logger=get_db_logger(),
    )


def get_model_segmentation_service() -> ModelSegmentationService:
    """Default ModelSegmentationService wiring for FastAPI ``Depends()``."""
    return ModelSegmentationService(
        ModelSegmentationRepository(),
        get_segmentation_data_store(),
        logger=get_db_logger(),
    )
