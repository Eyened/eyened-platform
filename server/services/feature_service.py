from __future__ import annotations

from eyened_orm import Feature
from eyened_orm.repositories.feature_repository import FeatureRepository
from eyened_orm.authz.scope import AccessScope
from fastapi import Depends
from sqlalchemy.orm import Session

from ..db import get_db
from .access_scope import get_access_scope
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import ConflictError, NotFoundError


class FeatureService:
    """Business logic for features and their composite (parent/child) links."""

    def __init__(
        self,
        repository: FeatureRepository,
        *,
        scope: AccessScope,
        audit: AuditService | None = None,
    ) -> None:
        self.repository = repository
        self.scope = scope
        self._actor = ActingUser.from_scope(scope)
        self.audit = audit

    def list_features(self, with_counts: bool) -> tuple[list[Feature], dict[int, int]]:
        """Return all features (name-sorted); counts is {} unless with_counts."""
        features = self.repository.list_all()
        counts = self.repository.segmentation_counts() if with_counts else {}
        return features, counts

    def get_feature(self, feature_id: int) -> Feature:
        """Return a feature by id.

        Raises:
            NotFoundError: If the feature does not exist.
        """
        feature = self.repository.get_by_id(feature_id)
        if feature is None:
            raise NotFoundError(f"Feature {feature_id} not found")
        return feature

    def create_feature(
        self, name: str, subfeature_ids: list[int] | None
    ) -> Feature:
        """Create a feature and set its subfeature links."""
        feature = Feature(FeatureName=name)
        self.repository.add(feature)
        self.repository.replace_subfeatures(feature.FeatureID, subfeature_ids)
        if self.audit is not None:
            self.audit.record(
                action="INSERT", entity="Feature", actor=self._actor,
                entity_id=feature.FeatureID,
                changes={"name": feature.FeatureName, "subfeature_ids": subfeature_ids or []},
            )
        return feature

    def update_feature(
        self, feature_id: int, name: str | None,
        subfeature_ids: list[int] | None,
    ) -> Feature:
        """Update a feature's name and/or subfeature links (each optional).

        Raises:
            NotFoundError: If the feature does not exist.
        """
        feature = self.repository.get_by_id(feature_id)
        if feature is None:
            raise NotFoundError(f"Feature {feature_id} not found")

        before = AuditService.snapshot(feature, "FeatureName")
        if name is not None:
            feature.FeatureName = name
        changes: dict = AuditService.diff(before, feature)
        self.repository.save(feature)
        if subfeature_ids is not None:
            current = self.repository.list_subfeature_ids(feature_id)
            # Link changes are not scalar attribute history — keep them explicit.
            changes["subfeature_ids"] = {"old": current, "new": subfeature_ids}
            self.repository.replace_subfeatures(feature_id, subfeature_ids)

        if self.audit is not None:
            self.audit.record(
                action="UPDATE", entity="Feature", actor=self._actor,
                entity_id=feature_id, changes=changes if changes else None,
            )
        return feature

    def delete_feature(self, feature_id: int) -> None:
        """Delete a feature, unless it is referenced by segmentations or is a child.

        Raises:
            NotFoundError: If the feature does not exist.
            ConflictError: If segmentations reference it (FEATURE_HAS_SEGMENTATIONS)
                or it is a child of another feature (FEATURE_IS_CHILD).
        """
        feature = self.repository.get_by_id(feature_id)
        if feature is None:
            raise NotFoundError(f"Feature {feature_id} not found")

        # count_segmentations is database-wide on purpose (it decides whether
        # the delete is legal, and deletion is global), so the number it
        # returns may include projects this caller cannot reach. It therefore
        # decides *whether* to refuse and never appears in the refusal: no
        # count in the message, and no count in the payload.
        if self.repository.count_segmentations(feature_id) > 0:
            raise ConflictError({
                "code": "FEATURE_HAS_SEGMENTATIONS",
                "message": (
                    f"Cannot delete feature '{feature.FeatureName}' because "
                    "segmentations reference it."
                ),
            })

        parents = self.repository.parent_names_of_child(feature_id)
        if parents:
            raise ConflictError({
                "code": "FEATURE_IS_CHILD",
                "message": (
                    f"Cannot delete feature '{feature.FeatureName}' because it is a "
                    f"child of {len(parents)} feature(s). Remove those links first."
                ),
                "parents": parents,
            })

        deleted_data = {"name": feature.FeatureName}
        self.repository.delete(feature)
        if self.audit is not None:
            self.audit.record(
                action="DELETE", entity="Feature", actor=self._actor,
                entity_id=feature_id, changes=deleted_data,
            )
        return None


def get_feature_service(
    db: Session = Depends(get_db),
    scope: AccessScope = Depends(get_access_scope),
) -> FeatureService:
    """Default FeatureService wiring for FastAPI ``Depends()``."""
    return FeatureService(
        FeatureRepository(db, scope=scope),
        scope=scope,
        audit=get_audit_service(db),
    )
