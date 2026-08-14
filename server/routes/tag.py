from fastapi import APIRouter, Depends, Response

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_aux import TagGET, TagPATCH, TagPUT
from ..services.acting_user import ActingUser
from ..services.tag_service import TagService, get_tag_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.post("/tags", response_model=TagGET)
async def create_tag(
    dto: TagPUT,
    service: TagService = Depends(get_tag_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a tag owned by the current user."""
    tag = service.create_tag(
        dto.name,
        dto.description,
        dto.tag_type,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.tag_to_get(tag)


@router.get("/tags", response_model=list[TagGET])
async def list_tags(
    service: TagService = Depends(get_tag_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return all tags."""
    return [DTOConverter.tag_to_get(t) for t in service.list_tags()]


@router.patch("/tags/{tag_id}", response_model=TagGET)
async def patch_tag(
    tag_id: int,
    dto: TagPATCH,
    service: TagService = Depends(get_tag_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a tag's name, description, and/or type."""
    tag = service.update_tag(
        tag_id,
        dto.name,
        dto.description,
        dto.tag_type,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.tag_to_get(tag)


@router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: int,
    service: TagService = Depends(get_tag_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a tag."""
    service.delete_tag(
        tag_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)


@router.post("/tags/{tag_id}/star", status_code=204)
async def star_tag(
    tag_id: int,
    service: TagService = Depends(get_tag_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Star a tag for the current user (idempotent)."""
    service.star_tag(
        tag_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)


@router.delete("/tags/{tag_id}/star", status_code=204)
async def unstar_tag(
    tag_id: int,
    service: TagService = Depends(get_tag_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove the current user's star from a tag (idempotent)."""
    service.unstar_tag(
        tag_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)
