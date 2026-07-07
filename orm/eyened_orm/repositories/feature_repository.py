from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from eyened_orm import Feature
from eyened_orm.segmentation import FeatureFeatureLink, Segmentation


class FeatureRepository:
    """Data access for Feature rows and their parent/child (composite) links."""

    def get_by_id(self, session: Session, feature_id: int) -> Feature | None:
        """Return the feature with the given id, or None if absent."""
        return session.get(Feature, feature_id)

    def list_all(self, session: Session) -> list[Feature]:
        """Return all features ordered by name (ascending)."""
        return list(
            session.scalars(select(Feature).order_by(Feature.FeatureName.asc())).all()
        )

    def segmentation_counts(self, session: Session) -> dict[int, int]:
        """Return {FeatureID: segmentation count} for features that have any."""
        rows = session.execute(
            select(Segmentation.FeatureID, func.count()).group_by(Segmentation.FeatureID)
        ).all()
        return {fid: cnt for fid, cnt in rows}

    def count_segmentations(self, session: Session, feature_id: int) -> int:
        """Return how many segmentations reference this feature."""
        return session.execute(
            select(func.count())
            .select_from(Segmentation)
            .where(Segmentation.FeatureID == feature_id)
        ).scalar_one()

    def parent_names_of_child(self, session: Session, feature_id: int) -> list[str]:
        """Return the names of features that list this feature as a child."""
        return list(
            session.execute(
                select(Feature.FeatureName)
                .join(
                    FeatureFeatureLink,
                    Feature.FeatureID == FeatureFeatureLink.ParentFeatureID,
                )
                .where(FeatureFeatureLink.ChildFeatureID == feature_id)
            )
            .scalars()
            .all()
        )

    def list_subfeature_ids(self, session: Session, feature_id: int) -> list[int]:
        """Return this feature's child ids, ordered by FeatureIndex."""
        return list(
            session.execute(
                select(FeatureFeatureLink.ChildFeatureID)
                .where(FeatureFeatureLink.ParentFeatureID == feature_id)
                .order_by(FeatureFeatureLink.FeatureIndex)
            )
            .scalars()
            .all()
        )

    def replace_subfeatures(
        self, session: Session, parent_id: int, sub_ids: list[int] | None
    ) -> None:
        """Replace all of a feature's child links with ``sub_ids`` (0-indexed).

        Deletes existing parent->child links, then re-adds one link per id in
        order. Flushes so a following read in the same transaction sees the new
        state; does not commit (the Service owns the transaction boundary).
        """
        session.execute(
            delete(FeatureFeatureLink).where(
                FeatureFeatureLink.ParentFeatureID == parent_id
            )
        )
        for idx, child_id in enumerate(sub_ids or []):
            session.add(
                FeatureFeatureLink(
                    ParentFeatureID=parent_id,
                    ChildFeatureID=child_id,
                    FeatureIndex=idx,
                )
            )
        session.flush()
