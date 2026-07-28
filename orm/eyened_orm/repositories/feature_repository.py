from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from eyened_orm import Feature
from eyened_orm.segmentation import FeatureFeatureLink, Segmentation


class FeatureRepository:
    """Data access for Feature rows and their parent/child (composite) links."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, feature: Feature) -> None:
        """Stage a new feature and flush so its PK is assigned."""
        self._session.add(feature)
        self._session.flush()

    def delete(self, feature: Feature) -> None:
        """Delete a feature and flush so integrity errors surface in-request."""
        self._session.delete(feature)
        self._session.flush()

    def get_by_id(self, feature_id: int) -> Feature | None:
        """Return the feature with the given id, or None if absent."""
        return self._session.get(Feature, feature_id)

    def save(self, feature: Feature) -> None:
        """Persist in-place mutations to ``feature`` within the request transaction.

        ``feature`` names what is being saved; the flush covers the whole unit
        of work, deliberately not just this row.
        """
        self._session.flush()

    def list_all(self) -> list[Feature]:
        """Return all features ordered by name (ascending)."""
        return list(
            self._session.scalars(
                select(Feature).order_by(Feature.FeatureName.asc())
            ).all()
        )

    def segmentation_counts(self) -> dict[int, int]:
        """Return {FeatureID: segmentation count} for features that have any."""
        rows = self._session.execute(
            select(Segmentation.FeatureID, func.count()).group_by(Segmentation.FeatureID)
        ).all()
        return {fid: cnt for fid, cnt in rows}

    def count_segmentations(self, feature_id: int) -> int:
        """Return how many segmentations reference this feature."""
        return self._session.execute(
            select(func.count())
            .select_from(Segmentation)
            .where(Segmentation.FeatureID == feature_id)
        ).scalar_one()

    def parent_names_of_child(self, feature_id: int) -> list[str]:
        """Return the names of features that list this feature as a child."""
        return list(
            self._session.execute(
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

    def list_subfeature_ids(self, feature_id: int) -> list[int]:
        """Return this feature's child ids, ordered by FeatureIndex."""
        return list(
            self._session.execute(
                select(FeatureFeatureLink.ChildFeatureID)
                .where(FeatureFeatureLink.ParentFeatureID == feature_id)
                .order_by(FeatureFeatureLink.FeatureIndex)
            )
            .scalars()
            .all()
        )

    def replace_subfeatures(self, parent_id: int, sub_ids: list[int] | None) -> None:
        """Replace all of a feature's child links with ``sub_ids`` (0-indexed).

        Deletes existing parent->child links, then re-adds one link per id in
        order. Flushes so a following read in the same transaction sees the new
        state; does not commit — this runs within the request transaction.
        """
        self._session.execute(
            delete(FeatureFeatureLink).where(
                FeatureFeatureLink.ParentFeatureID == parent_id
            )
        )
        for idx, child_id in enumerate(sub_ids or []):
            self._session.add(
                FeatureFeatureLink(
                    ParentFeatureID=parent_id,
                    ChildFeatureID=child_id,
                    FeatureIndex=idx,
                )
            )
        self._session.flush()
