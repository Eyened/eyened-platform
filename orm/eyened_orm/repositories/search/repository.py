"""Pure query construction for the search surfaces.

Framework-agnostic SQLAlchemy: takes a Session and already-resolved ORM
predicates, returns rows and counts. UI vocabulary never reaches this module --
callers resolve labels to ORM attributes before calling in.

Carries three known query-shape inefficiencies verbatim (the attribute-def N+1,
the OR-of-joins EXISTS, and the redundant DISTINCT in instances_for_studies).
They are deliberate follow-up work, gated on an EXPLAIN ANALYZE baseline against
real MySQL; the SQLite suite can prove rows are unchanged but not that a rewrite
is faster. Do not "fix" them here.
"""
from __future__ import annotations

from typing import Any, List, Literal

from eyened_orm import ImageInstance, Series, Study
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .conditions import AttributeConditionSpec, ResolvedCondition
from .exists import resolve_attribute_definitions as _resolve_attribute_definitions
from .selects import (
    build_instance_select,
    build_study_select,
    instance_filtered_select,
    instance_options,
    study_filtered_select,
    study_options,
)


class SearchRepository:
    """Query construction and execution for instance and study search."""

    def search_instances(
        self,
        session: Session,
        *,
        conditions: List[ResolvedCondition],
        attr_conditions: List[AttributeConditionSpec],
        order_by: Any,
        order: Literal["ASC", "DESC"],
        limit: int,
        offset: int,
    ) -> List[ImageInstance]:
        """Return instances matching the conditions, ordered and windowed."""
        stmt = build_instance_select(
            session, conditions, attr_conditions, order_by, order
        )
        return list(
            session.execute(
                stmt.options(*instance_options()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )

    def count_instances(
        self,
        session: Session,
        *,
        conditions: List[ResolvedCondition],
        attr_conditions: List[AttributeConditionSpec],
    ) -> int:
        """Count instances matching the same predicate ``search_instances`` applies."""
        stmt = instance_filtered_select(session, conditions, attr_conditions)
        return session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

    def resolve_attribute_definitions(
        self, session: Session, specs: List[AttributeConditionSpec]
    ) -> dict:
        """Resolve attribute specs to their definitions, keyed by (model, attr, feature).

        A spec whose definition does not resolve is absent from the result -- the
        service inspects this to reject unresolvable attributes rather than silently
        dropping the filter. Data access only; the HTTP-status policy stays upstream.
        """
        keys = [(s.model, s.attribute, s.feature) for s in specs]
        return _resolve_attribute_definitions(session, keys)

    def search_studies(
        self,
        session: Session,
        *,
        conditions: List[ResolvedCondition],
        order_by: Any,
        order: Literal["ASC", "DESC"],
        limit: int,
        offset: int,
    ) -> List[Study]:
        """Return studies matching the conditions, ordered and windowed."""
        stmt = build_study_select(conditions, order_by, order)
        return list(
            session.execute(
                stmt.options(*study_options()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )

    def count_studies(
        self,
        session: Session,
        *,
        conditions: List[ResolvedCondition],
    ) -> int:
        """Count studies matching the same predicate ``search_studies`` applies."""
        stmt = study_filtered_select(conditions)
        return session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

    def instances_for_studies(
        self, session: Session, study_ids: List[int]
    ) -> List[ImageInstance]:
        """Return the active instances of the given studies (empty list for no ids)."""
        if not study_ids:
            return []
        stmt = (
            select(ImageInstance)
            .where(~ImageInstance.Inactive)
            .join(Series, ImageInstance.SeriesID == Series.SeriesID)
            .where(Series.StudyID.in_(study_ids))
            .options(*instance_options())
            .distinct()
        )
        return list(session.execute(stmt).scalars().all())
