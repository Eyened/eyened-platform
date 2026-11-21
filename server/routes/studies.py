import httpxyz
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_aux import ObjectTagPATCH, ObjectTagPOST, TagMeta
from ..services.data_source_client import fetch_data_source, get_data_source_client
from ..services.study_service import StudyService, get_study_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.post("/studies/{study_id}/tags", response_model=TagMeta)
def tag_study(
    study_id: int,
    body: ObjectTagPOST,
    service: StudyService = Depends(get_study_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Attach a Tag to a Study by tag ID (idempotent)."""
    link = service.tag_study(
        study_id,
        body.tag_id,
        body.comment,
    )
    return DTOConverter.link_to_tag_metadata(link)


@router.delete("/studies/{study_id}/tags/{tag_id}", status_code=204)
def untag_study(
    study_id: int,
    tag_id: int,
    service: StudyService = Depends(get_study_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove a Tag from a Study (idempotent)."""
    service.untag_study(
        study_id,
        tag_id,
    )
    return Response(status_code=204)


@router.patch("/studies/{study_id}/tags/{tag_id}", response_model=TagMeta)
def patch_study_tag(
    study_id: int,
    tag_id: int,
    body: ObjectTagPATCH,
    service: StudyService = Depends(get_study_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Update comment on an existing Study tag link."""
    link = service.patch_study_tag(
        study_id,
        tag_id,
        body.comment,
    )
    return DTOConverter.link_to_tag_metadata(link)


@router.get("/studies/{study_id}/data-sources/{name}")
async def get_study_data_source(
    study_id: int,
    name: str,
    service: StudyService = Depends(get_study_service),
    db: Session = Depends(get_db),
    client: httpxyz.AsyncClient = Depends(get_data_source_client),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """This study's data from an external source, proxied unchanged."""
    url = await run_in_threadpool(service.data_source_url, study_id, name)
    # Return the DB connection to the pool before waiting on the upstream.
    await run_in_threadpool(db.commit)
    body = await fetch_data_source(client, name, url)
    return Response(body, media_type="application/json")
