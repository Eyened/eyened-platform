"""Search orchestration: the RBAC seam.

Read-only: no ActingUser, no audit logger, no commit(). Takes explicit keyword
arguments rather than the route's Pydantic ``SearchQuery`` -- importing that
would invert the routes -> services dependency arrow. ``SearchQuery.model_dump()``
unpacks to exactly this signature. DTO conversion stays behind in the route; this
layer returns ORM rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from eyened_orm import (
    Creator,
    DeviceModel,
    Feature,
    FormAnnotation,
    FormAnnotationTagLink,
    FormSchema,
    ImageInstance,
    ImageInstanceTagLink,
    Project,
    SegmentationTagLink,
    Series,
    Study,
    StudyTagLink,
    Tag,
)
from eyened_orm.attributes import (
    AttributeDataType,
    AttributesModel,
    AttributesModelOutput,
)
from eyened_orm.attributes import AttributeDefinition as AttrDef
from eyened_orm.image_instance import ETDRSField as ImgETDRS
from eyened_orm.image_instance import Laterality as ImgLaterality
from eyened_orm.image_instance import Modality as ImgModality
from eyened_orm.patient import SexEnum as PatientSex
from eyened_orm.repositories.search import SearchRepository
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

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


def _query_tag_names(session: Session, link_table: Any) -> List[str]:
    """Helper to query distinct tag names from a link table."""
    return sorted(
        session.scalars(
            select(Tag.TagName).join(link_table, link_table.TagID == Tag.TagID).distinct()
        ).all()
    )


class SearchService:
    """Orchestrates search: translate the DSL, query, paginate, derive, count."""

    def __init__(self, repository: SearchRepository) -> None:
        self.repository = repository

    def search_instances(
        self,
        session: Session,
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
        attr_defs: dict[tuple[str | None, str, str | None], Any] = {}
        if attr_conds:
            # Resolved once here and handed to both the search and the count: the
            # resolution is an N+1, so rebuilding it per select tripled the queries.
            attr_defs = self.repository.resolve_attribute_definitions(session, attr_conds)
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
            session,
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

        studies = self._studies_for(session, instances)
        count = None
        if include_count:
            count = self.repository.count_instances(
                session,
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
        session: Session,
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
            session,
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
        instances = self.repository.instances_for_studies(session, study_ids)

        count = None
        if include_count:
            count = self.repository.count_studies(session, conditions=static_conds)

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

    def _studies_for(
        self, session: Session, instances: list[ImageInstance]
    ) -> List[Study]:
        """Distinct studies of the instances, in first-appearance order, series-loaded."""
        seen: set[int] = set()
        study_ids_ordered: list[int] = []
        for inst in instances:
            st = inst.Series.Study if inst.Series and inst.Series.Study else None
            if st and st.StudyID not in seen:
                seen.add(st.StudyID)
                study_ids_ordered.append(st.StudyID)

        if not study_ids_ordered:
            return []

        studies_stmt = (
            select(Study)
            .where(Study.StudyID.in_(study_ids_ordered))
            .options(
                selectinload(Study.Series).selectinload(
                    Series.ImageInstances.and_(~ImageInstance.Inactive)
                )
            )
        )
        studies = list(session.execute(studies_stmt).scalars().all())
        s_order = {sid: i for i, sid in enumerate(study_ids_ordered)}
        studies.sort(key=lambda s: s_order[s.StudyID])
        return studies

    def instance_signature(self, session: Session) -> List[SignatureField]:
        """Return signature metadata for instance search fields."""
        creator_names = sorted(
            Creator.query_column(session, Creator.CreatorName, where=(Creator.IsHuman == True))
        )
        items: list[SignatureField] = [
            # Enum-backed
            SignatureField(name="Laterality", values=[e.value for e in ImgLaterality], nullable=True),
            SignatureField(name="Modality", values=[e.value for e in ImgModality], nullable=True),
            SignatureField(name="ETDRS Field", values=[e.value for e in ImgETDRS], nullable=True),
            SignatureField(name="Patient Sex", values=[e.value for e in PatientSex], nullable=True),
            # DB-derived simple columns
            SignatureField(name="Project Name", values=sorted(Project.query_column(session, Project.ProjectName))),
            SignatureField(
                name="Device Model ID",
                values=[str(v) for v in sorted(DeviceModel.query_column(session, DeviceModel.DeviceModelID))],
            ),
            SignatureField(
                name="Segmentation Feature Name",
                values=sorted(Feature.query_column(session, Feature.FeatureName)),
            ),
            SignatureField(
                name="Segmentation Creator Name",
                values=creator_names,
            ),
            SignatureField(name="Segmentation Tag Name", values=_query_tag_names(session, SegmentationTagLink)),
            SignatureField(
                name="Form Schema Name",
                values=sorted(FormSchema.query_column(session, FormSchema.SchemaName)),
            ),
            SignatureField(
                name="Form Creator Name",
                values=creator_names,
            ),
            SignatureField(name="Form Tag Name", values=_query_tag_names(session, FormAnnotationTagLink)),
            SignatureField(name="Image Tag Name", values=_query_tag_names(session, ImageInstanceTagLink)),
        ]

        # Attributes
        attr_query = (
            select(
                AttrDef.AttributeName,
                AttrDef.AttributeDataType,
                AttributesModel.ModelName,
            )
            .select_from(AttrDef)
            .outerjoin(AttributesModelOutput, AttrDef.AttributeID == AttributesModelOutput.AttributeID)
            .outerjoin(AttributesModel, AttributesModelOutput.ModelID == AttributesModel.ModelID)
            .where(AttrDef.AttributeDataType != AttributeDataType.JSON)
            .distinct()
        )
        attr_rows = session.execute(attr_query).all()

        # Convert to SignatureFields
        dtype_map = {
            AttributeDataType.String: "string",
            AttributeDataType.Int: "int",
            AttributeDataType.Float: "float",
        }
        for name, dtype, model_name in attr_rows:
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

    def study_signature(self, session: Session) -> List[SignatureField]:
        """Return signature metadata for study search fields."""
        items: list[SignatureField] = []

        # Enum-backed
        items.append(
            SignatureField(
                name="Patient Sex", values=[e.value for e in PatientSex], nullable=True
            )
        )

        # DB-derived
        projects = session.execute(select(Project.ProjectName).distinct()).scalars().all()
        items.append(SignatureField(name="Project Name", values=sorted(projects)))

        form_schema_names = (
            session.execute(select(FormSchema.SchemaName).distinct()).scalars().all()
        )
        items.append(
            SignatureField(name="Form Schema Name", values=sorted(form_schema_names))
        )

        form_creators = (
            session.execute(
                select(Creator.CreatorName)
                .join(FormAnnotation, FormAnnotation.CreatorID == Creator.CreatorID)
                .where(~FormAnnotation.Inactive)
                .distinct()
            )
            .scalars()
            .all()
        )
        items.append(SignatureField(name="Form Creator Name", values=sorted(form_creators)))

        form_tag_names = (
            session.execute(
                select(Tag.TagName)
                .join(FormAnnotationTagLink, FormAnnotationTagLink.TagID == Tag.TagID)
                .distinct()
            )
            .scalars()
            .all()
        )
        items.append(SignatureField(name="Form Tag Name", values=sorted(form_tag_names)))

        study_tag_names = (
            session.execute(
                select(Tag.TagName)
                .join(StudyTagLink, StudyTagLink.TagID == Tag.TagID)
                .distinct()
            )
            .scalars()
            .all()
        )
        items.append(SignatureField(name="Study Tag Name", values=sorted(study_tag_names)))

        # Typed free-entry fields
        items.append(SignatureField(name="Study Date", values="date"))
        items.append(
            SignatureField(name="Study Description", values="string", nullable=True)
        )
        items.append(SignatureField(name="Study Round", values="int", nullable=True))
        items.append(SignatureField(name="Study Instance UID", values="string"))
        items.append(SignatureField(name="Patient Identifier", values="string", multi=True))
        items.append(SignatureField(name="Patient Birthdate", values="date", nullable=True))

        return items


def get_search_service() -> SearchService:
    """FastAPI dependency: a SearchService wired to its repository."""
    return SearchService(SearchRepository())
