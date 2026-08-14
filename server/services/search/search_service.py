"""Search orchestration: the RBAC seam.

Read-only: no ActingUser, no audit logger, no commit(). Takes explicit keyword
arguments rather than the route's Pydantic ``SearchQuery`` -- importing that
would invert the routes -> services dependency arrow. ``SearchQuery.model_dump()``
unpacks to exactly this signature. DTO conversion stays behind in the route; this
layer returns ORM rows.

No ``select()`` is built here: query construction belongs to ``SearchRepository``.
Column enumeration (``Model.query_column``) also goes through the repository, via
its thin ``column_values`` wrapper, so this module never touches a ``Session``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from eyened_orm import (
    Creator,
    DeviceModel,
    Feature,
    FormAnnotationTagLink,
    FormSchema,
    ImageInstance,
    ImageInstanceTagLink,
    Project,
    SegmentationTagLink,
    Study,
    StudyTagLink,
)
from eyened_orm.attributes import AttributeDataType, AttributeDefinition
from eyened_orm.image_instance import ETDRSField as ImgETDRS
from eyened_orm.image_instance import Laterality as ImgLaterality
from eyened_orm.image_instance import Modality as ImgModality
from eyened_orm.patient import SexEnum as PatientSex
from eyened_orm.repositories.search import SearchRepository
from fastapi import Depends
from sqlalchemy.orm import Session

from ...db import get_db
from ..exceptions import BadRequestError
from .conditions import translate_instance_conditions, translate_study_conditions
from .fields import (
    SignatureField,
    instance_order_by_fields_map,
    study_order_by_fields_map,
)


@dataclass
class InstanceSearchResult:
    instances: List[ImageInstance] = field(default_factory=list)
    studies: List[Study] = field(default_factory=list)
    count: int | None = None
    has_more: bool = False
    limit: int = 200
    page: int = 0


@dataclass
class StudySearchResult:
    studies: List[Study] = field(default_factory=list)
    instances: List[ImageInstance] = field(default_factory=list)
    count: int | None = None
    has_more: bool = False
    limit: int = 200
    page: int = 0


class SearchService:
    """Orchestrates search: translate the DSL, query, paginate, derive, count."""

    def __init__(self, repository: SearchRepository) -> None:
        self.repository = repository

    def search_instances(
        self,
        *,
        conditions: list[dict[str, Any]],
        order_by: str,
        order: str,
        limit: int = 200,
        page: int = 0,
        include_count: bool = False,
    ) -> InstanceSearchResult:
        """Search instances, derive their studies, and optionally count the total."""
        static_conds, attr_conds = translate_instance_conditions(conditions)
        attr_defs: dict[tuple[str | None, str, str | None], AttributeDefinition] = {}
        if attr_conds:
            # Resolved once here and handed to both the search and the count: the
            # resolution is an N+1, so rebuilding it per select tripled the queries.
            attr_defs = self.repository.resolve_attribute_definitions(attr_conds)
            missing = [
                spec.attribute
                for spec in attr_conds
                if (spec.model, spec.attribute, spec.feature) not in attr_defs
            ]
            if missing:
                # Name the fix, not just the failure: the signature endpoint is the
                # authoritative list of attributes this surface accepts. A dropped
                # attribute filter would otherwise return the whole result set.
                raise BadRequestError(
                    f"Unknown search attribute(s): {', '.join(sorted(set(missing)))}. "
                    f"See GET /instances/search/signature for the available attributes."
                )
        # RBAC Step 2 seam: append the visible-project predicate for the acting
        # user to `static_conds` here -- this is the one place both the search and
        # the count read, so a filter added here cannot be bypassed by either.
        # Inert pass-through today.
        offset = limit * page

        rows = self.repository.search_instances(
            conditions=static_conds,
            attr_conditions=attr_conds,
            attr_defs=attr_defs,
            order_by=instance_order_by_fields_map[order_by],
            order=order,
            limit=limit + 1,  # lookahead: one extra row answers has_more
            offset=offset,
        )
        has_more = len(rows) > limit
        instances = rows[:limit] if has_more else rows

        if not instances:
            return InstanceSearchResult(limit=limit, page=page)

        studies = self._studies_for(instances)
        count = None
        if include_count:
            count = self.repository.count_instances(
                conditions=static_conds,
                attr_conditions=attr_conds,
                attr_defs=attr_defs,
            )
        return InstanceSearchResult(
            instances=list(instances),
            studies=studies,
            count=count,
            has_more=has_more,
            limit=limit,
            page=page,
        )

    def search_studies(
        self,
        *,
        conditions: list[dict[str, Any]],
        order_by: str,
        order: str,
        limit: int = 200,
        page: int = 0,
        include_count: bool = False,
    ) -> StudySearchResult:
        """Search studies, then load their active instances, and optionally count."""
        static_conds = translate_study_conditions(conditions)
        # RBAC Step 2 seam (studies surface): append the visible-project predicate
        # to `static_conds` here. Inert pass-through today.
        offset = limit * page

        rows = self.repository.search_studies(
            conditions=static_conds,
            order_by=study_order_by_fields_map[order_by],
            order=order,
            limit=limit + 1,  # lookahead
            offset=offset,
        )
        has_more = len(rows) > limit
        studies = rows[:limit] if has_more else rows

        if not studies:
            return StudySearchResult(limit=limit, page=page)

        study_ids = [s.StudyID for s in studies]
        instances = self.repository.instances_for_studies(study_ids)

        count = None
        if include_count:
            count = self.repository.count_studies(conditions=static_conds)

        s_order = {sid: idx for idx, sid in enumerate(study_ids)}
        studies = sorted(studies, key=lambda s: s_order[s.StudyID])
        return StudySearchResult(
            studies=list(studies),
            instances=list(instances),
            count=count,
            has_more=has_more,
            limit=limit,
            page=page,
        )

    def _studies_for(self, instances: list[ImageInstance]) -> List[Study]:
        """Distinct studies of the instances, in first-appearance order, series-loaded."""
        seen: set[int] = set()
        study_ids_ordered: list[int] = []
        for inst in instances:
            st = inst.Series.Study if inst.Series and inst.Series.Study else None
            if st and st.StudyID not in seen:
                seen.add(st.StudyID)
                study_ids_ordered.append(st.StudyID)

        studies = self.repository.studies_by_ids(study_ids_ordered)
        s_order = {sid: i for i, sid in enumerate(study_ids_ordered)}
        studies.sort(key=lambda s: s_order[s.StudyID])
        return studies

    def instance_signature(self) -> List[SignatureField]:
        """Return signature metadata for instance search fields."""
        creator_names = sorted(
            self.repository.column_values(
                Creator, Creator.CreatorName, where=(Creator.IsHuman == True)
            )
        )
        items: list[SignatureField] = [
            # Enum-backed
            SignatureField(name="Laterality", values=[e.value for e in ImgLaterality], nullable=True),
            SignatureField(name="Modality", values=[e.value for e in ImgModality], nullable=True),
            SignatureField(name="ETDRS Field", values=[e.value for e in ImgETDRS], nullable=True),
            SignatureField(name="Patient Sex", values=[e.value for e in PatientSex], nullable=True),
            # DB-derived simple columns
            SignatureField(
                name="Project Name",
                values=sorted(self.repository.column_values(Project, Project.ProjectName)),
            ),
            SignatureField(
                name="Device Model ID",
                values=[
                    str(v)
                    for v in sorted(
                        self.repository.column_values(DeviceModel, DeviceModel.DeviceModelID)
                    )
                ],
            ),
            SignatureField(
                name="Segmentation Feature Name",
                values=sorted(self.repository.column_values(Feature, Feature.FeatureName)),
            ),
            SignatureField(
                name="Segmentation Creator Name",
                values=creator_names,
            ),
            SignatureField(
                name="Segmentation Tag Name",
                values=self.repository.tag_names(SegmentationTagLink),
            ),
            SignatureField(
                name="Form Schema Name",
                values=sorted(self.repository.column_values(FormSchema, FormSchema.SchemaName)),
            ),
            SignatureField(
                name="Form Creator Name",
                values=creator_names,
            ),
            SignatureField(
                name="Form Tag Name",
                values=self.repository.tag_names(FormAnnotationTagLink),
            ),
            SignatureField(
                name="Image Tag Name",
                values=self.repository.tag_names(ImageInstanceTagLink),
            ),
        ]

        # Convert attribute rows to SignatureFields
        dtype_map = {
            AttributeDataType.String: "string",
            AttributeDataType.Int: "int",
            AttributeDataType.Float: "float",
        }
        for name, dtype, model_name in self.repository.attribute_signature_rows():
            items.append(
                SignatureField(
                    name=name,
                    values=dtype_map.get(dtype, "string"),
                    type="attribute",
                    model=model_name,
                )
            )
        # Free-text/number defaults
        items.extend([
            SignatureField(name="Image DBID", values="int"),
            SignatureField(name="Color Fundus Quality", values="float", nullable=True),
            SignatureField(name="Study Date", values="date"),
            SignatureField(name="Patient Identifier", values="string", multi=True),
            SignatureField(name="Patient Birthdate", values="date", nullable=True),
        ])

        return items

    def study_signature(self) -> List[SignatureField]:
        """Return signature metadata for study search fields.

        NOTE: like ``instance_signature``, this enumerates every project, creator and
        tag in the database -- it does not pass through the ``static_conds`` seam.
        RBAC Step 2 must filter here too; the characterization tests pin today's
        cross-project behavior.
        """
        items: list[SignatureField] = [
            # Enum-backed
            SignatureField(
                name="Patient Sex", values=[e.value for e in PatientSex], nullable=True
            ),
            # DB-derived
            SignatureField(
                name="Project Name",
                values=sorted(self.repository.column_values(Project, Project.ProjectName)),
            ),
            SignatureField(
                name="Form Schema Name",
                values=sorted(self.repository.column_values(FormSchema, FormSchema.SchemaName)),
            ),
            SignatureField(
                name="Form Creator Name",
                values=self.repository.active_form_creator_names(),
            ),
            SignatureField(
                name="Form Tag Name",
                values=self.repository.tag_names(FormAnnotationTagLink),
            ),
            SignatureField(
                name="Study Tag Name",
                values=self.repository.tag_names(StudyTagLink),
            ),
            # Typed free-entry fields
            SignatureField(name="Study Date", values="date"),
            SignatureField(name="Study Description", values="string", nullable=True),
            SignatureField(name="Study Round", values="int", nullable=True),
            SignatureField(name="Study Instance UID", values="string"),
            SignatureField(name="Patient Identifier", values="string", multi=True),
            SignatureField(name="Patient Birthdate", values="date", nullable=True),
        ]
        return items


def get_search_service(db: Session = Depends(get_db)) -> SearchService:
    """FastAPI dependency: a SearchService wired to its repository."""
    return SearchService(SearchRepository(db))
