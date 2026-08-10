"""Pure query construction for the search surfaces.

Framework-agnostic SQLAlchemy: takes a Session and already-resolved ORM
predicates, returns rows and counts. UI vocabulary never reaches this module --
callers resolve labels to ORM attributes before calling in.

Carries three known query-shape inefficiencies verbatim (the attribute-def N+1,
the OR-of-joins EXISTS, and the redundant DISTINCT in instances_for_studies).
They are deliberate follow-up work, gated on an EXPLAIN ANALYZE baseline against
real MySQL; the SQLite suite can prove rows are unchanged but not that a rewrite
is faster. Do not "fix" them here.

Read-scoping coverage of SearchRepository's eleven public methods:

Six row/count-returning methods apply apply_scope() before executing and
return only rows the caller's project memberships allow: search_instances,
count_instances, search_studies, count_studies, studies_by_ids,
instances_for_studies.

Four methods are deliberately unfiltered: they read non-project vocabulary
with no project anchor to scope against -- tag_names,
active_form_creator_names, attribute_signature_rows,
resolve_attribute_definitions.

column_values is unfiltered too, but it is NOT on the safe list above and is
NOT deliberately unfiltered -- it is a known, unfixed gap owned by Task 13a
(a separate unit of work that runs before the read-scoping coverage guard).
column_values is a generic column-values wrapper, and whether a given call
leaks project data depends entirely on what the caller passes it. Its call
sites that pass Project enumerate every project's name in the database into
a search-form dropdown, regardless of the caller's memberships. Fixing it
means filtering Project.ProjectID at the caller, which this module's scoping
cannot reach today, since Project has no anchor route of its own to route
through.
"""
from __future__ import annotations

from typing import Any, List, Literal, Optional, Tuple

from eyened_orm import Creator, FormAnnotation, ImageInstance, Series, Study, Tag
from eyened_orm.attributes import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModel,
    AttributesModelOutput,
)
from eyened_orm.authz.scope import AccessScope
from eyened_orm.authz.scoping import apply_scope
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

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

    def search_instances(
        self,
        *,
        conditions: List[ResolvedCondition],
        attr_conditions: List[AttributeConditionSpec],
        attr_defs: dict[tuple[str | None, str, str | None], AttributeDefinition],
        order_by: Any,
        order: Literal["ASC", "DESC"],
        limit: int,
        offset: int,
    ) -> List[ImageInstance]:
        """Return instances matching the conditions, ordered and windowed.

        ``attr_defs`` comes from ``resolve_attribute_definitions``; the caller
        resolves once and passes the same map to ``count_instances`` so the two
        agree without paying for the resolution twice.
        """
        stmt = build_instance_select(
            conditions, attr_conditions, attr_defs, order_by, order
        )
        stmt = apply_scope(stmt, ImageInstance, self._scope)
        return list(
            self._session.execute(
                stmt.options(*instance_options()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )

    def count_instances(
        self,
        *,
        conditions: List[ResolvedCondition],
        attr_conditions: List[AttributeConditionSpec],
        attr_defs: dict[tuple[str | None, str, str | None], AttributeDefinition],
    ) -> int:
        """Count instances matching the same predicate ``search_instances`` applies."""
        stmt = instance_filtered_select(conditions, attr_conditions, attr_defs)
        stmt = apply_scope(stmt, ImageInstance, self._scope)
        return self._session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

    def resolve_attribute_definitions(
        self, specs: List[AttributeConditionSpec]
    ) -> dict[tuple[str | None, str, str | None], AttributeDefinition]:
        """Resolve attribute specs to their definitions, keyed by (model, attr, feature).

        A spec whose definition does not resolve is absent from the result -- the
        service inspects this to reject unresolvable attributes rather than silently
        dropping the filter. Data access only; the HTTP-status policy stays upstream.
        """
        keys = [(s.model, s.attribute, s.feature) for s in specs]
        return _resolve_attribute_definitions(self._session, keys)

    def search_studies(
        self,
        *,
        conditions: List[ResolvedCondition],
        order_by: Any,
        order: Literal["ASC", "DESC"],
        limit: int,
        offset: int,
    ) -> List[Study]:
        """Return studies matching the conditions, ordered and windowed."""
        stmt = build_study_select(conditions, order_by, order)
        stmt = apply_scope(stmt, Study, self._scope)
        return list(
            self._session.execute(
                stmt.options(*study_options()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )

    def count_studies(
        self,
        *,
        conditions: List[ResolvedCondition],
    ) -> int:
        """Count studies matching the same predicate ``search_studies`` applies."""
        stmt = study_filtered_select(conditions)
        stmt = apply_scope(stmt, Study, self._scope)
        return self._session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

    def tag_names(self, link_table: Any) -> List[str]:
        """Distinct tag names reachable through the given tag link table, sorted."""
        return sorted(
            self._session.scalars(
                select(Tag.TagName)
                .join(link_table, link_table.TagID == Tag.TagID)
                .distinct()
            ).all()
        )

    def active_form_creator_names(self) -> List[str]:
        """Names of creators with at least one active form annotation, sorted."""
        return sorted(
            self._session.scalars(
                select(Creator.CreatorName)
                .join(FormAnnotation, FormAnnotation.CreatorID == Creator.CreatorID)
                .where(~FormAnnotation.Inactive)
                .distinct()
            ).all()
        )

    def attribute_signature_rows(
        self,
    ) -> List[Tuple[str, AttributeDataType, Optional[str]]]:
        """(AttributeName, AttributeDataType, ModelName) for every non-JSON attribute.

        Model-less attributes carry ModelName None; an attribute produced by several
        models yields one row per model, exactly as the signature endpoint expects.
        """
        stmt = (
            select(
                AttributeDefinition.AttributeName,
                AttributeDefinition.AttributeDataType,
                AttributesModel.ModelName,
            )
            .select_from(AttributeDefinition)
            .outerjoin(
                AttributesModelOutput,
                AttributeDefinition.AttributeID == AttributesModelOutput.AttributeID,
            )
            .outerjoin(
                AttributesModel,
                AttributesModelOutput.ModelID == AttributesModel.ModelID,
            )
            .where(AttributeDefinition.AttributeDataType != AttributeDataType.JSON)
            .distinct()
        )
        return [tuple(row) for row in self._session.execute(stmt).all()]

    def studies_by_ids(self, study_ids: List[int]) -> List[Study]:
        """Return the given studies with their active instances eager-loaded.

        Unordered -- the caller owns the ordering, which on the instances surface
        is the instances' first-appearance order and not a property of the query.
        """
        if not study_ids:
            return []
        stmt = (
            select(Study)
            .where(Study.StudyID.in_(study_ids))
            .options(*study_options())
        )
        stmt = apply_scope(stmt, Study, self._scope)
        return list(self._session.execute(stmt).scalars().all())

    def instances_for_studies(self, study_ids: List[int]) -> List[ImageInstance]:
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
        stmt = apply_scope(stmt, ImageInstance, self._scope)
        return list(self._session.execute(stmt).scalars().all())

    def column_values(self, model: Any, column: Any, *, where: Any = None) -> List[Any]:
        """Distinct values of a column on ``model`` (thin wrapper over ``Model.query_column``).

        Lets the service enumerate a reference column (e.g. ``Creator.CreatorName``)
        without touching a ``Session`` directly.
        """
        return model.query_column(self._session, column, where=where)
