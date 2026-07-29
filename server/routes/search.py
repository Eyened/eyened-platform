"""Search endpoints: thin HTTP handlers over SearchService.

The query construction, vocabulary, DSL translation and orchestration live in
``server.services.search`` and ``eyened_orm.repositories.search``. This module
keeps only the HTTP contracts and the four handlers, which translate the request,
call the service, and render DTOs. ``router`` keeps its name and import path, so
``server.main`` needs no change.
"""
from datetime import date
from typing import Annotated, List, Literal, Optional, Union

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..dtos import ImageGET, StudyGET
from ..dtos.dto_converter import DTOConverter
from ..services.search import (
    SearchService,
    SignatureField,
    get_search_service,
    instance_order_by_fields,
    operators,
    searchable_fields,
    study_order_by_fields,
    study_searchable_fields,
)
from .auth import CurrentUser, get_current_user

router = APIRouter()


class DefaultCondition(BaseModel):
    type: Literal["default"] = "default"
    variable: searchable_fields
    operator: operators
    value: Union[date, int, float, str, list[str], None]


class AttributeCondition(BaseModel):
    type: Literal["attribute"]
    model: Optional[str] = None
    variable: str
    operator: operators
    value: Union[int, float, str, list[str], None]
    feature: Optional[str] = None  # NEW: filter by feature name


SearchCondition = Annotated[
    Union[DefaultCondition, AttributeCondition], Field(discriminator="type")
]


class SearchQuery(BaseModel):
    conditions: List[SearchCondition]
    limit: int = 200
    page: int = 0
    order_by: instance_order_by_fields
    order: Literal["ASC", "DESC"] = "ASC"
    include_count: bool = False


class SearchResponse(BaseModel):
    instances: List[ImageGET]
    studies: List[StudyGET]
    limit: int
    page: int
    count: Optional[int] = None
    result_ids: List[str]
    has_more: bool


# Study search DTOs
class StudySearchCondition(BaseModel):
    variable: study_searchable_fields
    operator: operators
    value: Union[date, int, float, str, list[str], None]  # add list[str]


class StudySearchQuery(BaseModel):
    conditions: List[StudySearchCondition]
    limit: int = 200
    page: int = 0
    order_by: study_order_by_fields
    order: Literal["ASC", "DESC"] = "ASC"
    include_count: bool = False


class StudySearchResponse(BaseModel):
    studies: List[StudyGET]
    instances: List[ImageGET]
    limit: int
    page: int
    count: Optional[int] = None
    result_ids: List[int]
    has_more: bool


@router.post(
    "/instances/search", response_model=SearchResponse, response_model_exclude_none=True
)
async def search_instances(
    query: SearchQuery,
    current_user: CurrentUser = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
):
    result = service.search_instances(**query.model_dump())
    return {
        "instances": [
            DTOConverter.image_instance_to_get(i, with_tag_metadata=True)
            for i in result.instances
        ],
        "studies": [
            DTOConverter.study_to_get(s, include_series=True, with_tag_metadata=True)
            for s in result.studies
        ],
        "limit": result.limit,
        "page": result.page,
        "count": result.count,
        "result_ids": [i.PublicID for i in result.instances],
        "has_more": result.has_more,
    }


@router.post(
    "/studies/search",
    response_model=StudySearchResponse,
    response_model_exclude_none=True,
)
async def search_studies(
    query: StudySearchQuery,
    current_user: CurrentUser = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
):
    result = service.search_studies(**query.model_dump())
    return {
        "studies": [
            DTOConverter.study_to_get(s, include_series=True, with_tag_metadata=True)
            for s in result.studies
        ],
        "instances": [
            DTOConverter.image_instance_to_get(i, with_tag_metadata=True)
            for i in result.instances
        ],
        "limit": result.limit,
        "page": result.page,
        "count": result.count,
        "result_ids": [s.StudyID for s in result.studies],
        "has_more": result.has_more,
    }


@router.get("/instances/search/signature", response_model=list[SignatureField])
async def instances_signature(
    current_user: CurrentUser = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
):
    """Return signature metadata for instance search fields."""
    return service.instance_signature()


@router.get("/studies/search/signature", response_model=list[SignatureField])
async def studies_signature(
    current_user: CurrentUser = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
):
    """Return signature metadata for study search fields."""
    return service.study_signature()
