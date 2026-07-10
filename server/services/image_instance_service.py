from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import ImageInstance
from eyened_orm.repositories.image_instance_repository import ImageInstanceRepository
from eyened_orm.repositories.tag_repository import TagRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .exceptions import NotFoundError


class ImageInstanceService:
    """Business logic for ImageInstance reads and its Tag links."""

    def __init__(
        self,
        repository: ImageInstanceRepository,
        tag_repository: TagRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.tags = tag_repository
        self.logger = logger

    def get_instance(
        self,
        session: Session,
        instance_id: int,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance:
        """Return an instance by int id, with the requested eager-load graph.

        Raises:
            NotFoundError: If the instance does not exist.
        """
        item = self.repository.get_full_graph_by_id(
            session,
            instance_id,
            with_segmentations=with_segmentations,
            with_form_annotations=with_form_annotations,
            with_model_segmentations=with_model_segmentations,
        )
        if item is None:
            raise NotFoundError("ImageInstance not found")
        return item

    def get_by_public_id(
        self,
        session: Session,
        image_id: str,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance:
        """Return an instance by PublicID, with the requested eager-load graph.

        Raises:
            NotFoundError: If the instance does not exist.
        """
        item = self.repository.get_full_graph_by_public_id(
            session,
            image_id,
            with_segmentations=with_segmentations,
            with_form_annotations=with_form_annotations,
            with_model_segmentations=with_model_segmentations,
        )
        if item is None:
            raise NotFoundError("ImageInstance not found")
        return item

    def get_for_storage(self, session: Session, public_id: str) -> ImageInstance:
        """Return the storage-loaded instance for a data/thumbnail request.

        Raises:
            NotFoundError: If the instance does not exist.
        """
        item = self.repository.get_with_storage_by_public_id(session, public_id)
        if item is None:
            raise NotFoundError("ImageInstance not found")
        return item


def get_image_instance_service() -> ImageInstanceService:
    """Default ImageInstanceService wiring for FastAPI ``Depends()``."""
    return ImageInstanceService(
        ImageInstanceRepository(), TagRepository(), logger=get_db_logger()
    )
