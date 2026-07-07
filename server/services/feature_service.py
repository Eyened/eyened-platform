from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import Feature
from eyened_orm.repositories.feature_repository import FeatureRepository

from ..utils.db_logging import DatabaseModificationLogger, get_db_logger
from .acting_user import ActingUser
from .exceptions import ConflictError, NotFoundError


class FeatureService:
    """Business logic for features and their composite (parent/child) links."""

    def __init__(
        self,
        repository: FeatureRepository,
        logger: DatabaseModificationLogger | None = None,
    ) -> None:
        self.repository = repository
        self.logger = logger

    def list_features(
        self, session: Session, with_counts: bool
    ) -> tuple[list[Feature], dict[int, int]]:
        """Return all features (name-sorted); counts is {} unless with_counts."""
        features = self.repository.list_all(session)
        counts = self.repository.segmentation_counts(session) if with_counts else {}
        return features, counts

    def get_feature(self, session: Session, feature_id: int) -> Feature:
        """Return a feature by id.

        Raises:
            NotFoundError: If the feature does not exist.
        """
        feature = self.repository.get_by_id(session, feature_id)
        if feature is None:
            raise NotFoundError(f"Feature {feature_id} not found")
        return feature

    def create_feature(
        self,
        session: Session,
        name: str,
        subfeature_ids: list[int] | None,
        actor: ActingUser,
    ) -> Feature:
        """Create a feature and set its subfeature links."""
        feature = Feature(FeatureName=name)
        session.add(feature)
        session.flush()
        self.repository.replace_subfeatures(session, feature.FeatureID, subfeature_ids)
        session.commit()
        session.refresh(feature)
        if self.logger is not None:
            self.logger.log_insert(
                user=actor.username,
                user_id=actor.id,
                endpoint="POST /api/features",
                entity="Feature",
                entity_id=feature.FeatureID,
                fields={"name": feature.FeatureName, "subfeature_ids": subfeature_ids or []},
            )
        return feature

    def update_feature(
        self,
        session: Session,
        feature_id: int,
        name: str | None,
        subfeature_ids: list[int] | None,
        actor: ActingUser,
    ) -> Feature:
        """Update a feature's name and/or subfeature links (each optional).

        Raises:
            NotFoundError: If the feature does not exist.
        """
        feature = self.repository.get_by_id(session, feature_id)
        if feature is None:
            raise NotFoundError(f"Feature {feature_id} not found")

        changes: dict[str, str] = {}
        if name is not None:
            changes["name"] = f"{feature.FeatureName} -> {name}"
            feature.FeatureName = name
        if subfeature_ids is not None:
            current = self.repository.list_subfeature_ids(session, feature_id)
            changes["subfeature_ids"] = f"{current} -> {subfeature_ids}"
            self.repository.replace_subfeatures(session, feature_id, subfeature_ids)

        session.commit()
        session.refresh(feature)
        if self.logger is not None:
            self.logger.log_update(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"PATCH /api/features/{feature_id}",
                entity="Feature",
                entity_id=feature_id,
                changes=changes if changes else None,
            )
        return feature

    def delete_feature(
        self, session: Session, feature_id: int, actor: ActingUser
    ) -> None:
        """Delete a feature, unless it is referenced by segmentations or is a child.

        Raises:
            NotFoundError: If the feature does not exist.
            ConflictError: If segmentations reference it (FEATURE_HAS_SEGMENTATIONS)
                or it is a child of another feature (FEATURE_IS_CHILD).
        """
        feature = self.repository.get_by_id(session, feature_id)
        if feature is None:
            raise NotFoundError(f"Feature {feature_id} not found")

        seg_count = self.repository.count_segmentations(session, feature_id)
        if seg_count > 0:
            raise ConflictError(
                {
                    "code": "FEATURE_HAS_SEGMENTATIONS",
                    "message": (
                        f"Cannot delete feature '{feature.FeatureName}' because it has "
                        f"{seg_count} linked segmentation(s)."
                    ),
                    "segmentation_count": seg_count,
                }
            )

        parents = self.repository.parent_names_of_child(session, feature_id)
        if parents:
            raise ConflictError(
                {
                    "code": "FEATURE_IS_CHILD",
                    "message": (
                        f"Cannot delete feature '{feature.FeatureName}' because it is a "
                        f"child of {len(parents)} feature(s). Remove those links first."
                    ),
                    "parents": parents,
                }
            )

        deleted_data = {"name": feature.FeatureName}
        session.delete(feature)
        session.commit()
        if self.logger is not None:
            self.logger.log_delete(
                user=actor.username,
                user_id=actor.id,
                endpoint=f"DELETE /api/features/{feature_id}",
                entity="Feature",
                entity_id=feature_id,
                deleted_data=deleted_data,
            )
        return None


def get_feature_service() -> FeatureService:
    """Default FeatureService wiring for FastAPI ``Depends()``."""
    return FeatureService(FeatureRepository(), logger=get_db_logger())
