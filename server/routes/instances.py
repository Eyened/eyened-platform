from typing import Optional

from eyened_orm.storage_access import resolve_image_data_ref, resolve_thumbnail_ref
from fastapi import APIRouter, Depends, HTTPException, Response

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_instances import ImageGET
from ..dtos.dtos_aux import ObjectTagPOST, ObjectTagPATCH, TagMeta
from ..services.acting_user import ActingUser
from ..services.image_instance_service import (
    ImageInstanceService,
    get_image_instance_service,
)
from .auth import CurrentUser, get_current_user, is_authenticated

router = APIRouter()


@router.get("/instances/{instance_id}", response_model=ImageGET)
async def get_instance(
    instance_id: int,
    with_segmentations: bool = False,
    with_form_annotations: bool = False,
    with_model_segmentations: bool = False,
    with_tag_metadata: bool = False,
    service: ImageInstanceService = Depends(get_image_instance_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single image instance by id, with optional related graphs."""
    item = service.get_instance(
        instance_id,
        with_segmentations=with_segmentations,
        with_form_annotations=with_form_annotations,
        with_model_segmentations=with_model_segmentations,
    )
    return DTOConverter.image_instance_to_get(
        item,
        with_tag_metadata=with_tag_metadata,
        with_segmentations=with_segmentations,
        with_form_annotations=with_form_annotations,
        with_model_segmentations=with_model_segmentations,
    )


@router.get("/images/{image_id}", response_model=ImageGET)
async def get_public_image(
    image_id: str,
    with_segmentations: bool = False,
    with_form_annotations: bool = False,
    with_model_segmentations: bool = False,
    with_tag_metadata: bool = False,
    service: ImageInstanceService = Depends(get_image_instance_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single image instance by PublicID, with optional related graphs."""
    item = service.get_by_public_id(
        image_id,
        with_segmentations=with_segmentations,
        with_form_annotations=with_form_annotations,
        with_model_segmentations=with_model_segmentations,
    )
    return DTOConverter.image_instance_to_get(
        item,
        with_tag_metadata=with_tag_metadata,
        with_segmentations=with_segmentations,
        with_form_annotations=with_form_annotations,
        with_model_segmentations=with_model_segmentations,
    )


def build_storage_redirect_response(path: str) -> Response:
    response = Response()
    response.headers["X-Accel-Redirect"] = path
    return response


@router.get("/images/{image_id}/data")
async def get_public_image_data(
    image_id: str,
    index: Optional[int] = None,
    meta: bool = False,
    _: bool = Depends(is_authenticated),
    service: ImageInstanceService = Depends(get_image_instance_service),
):
    """Redirect to the stored image data for an instance (by PublicID)."""
    item = service.get_for_storage(image_id)
    if index is not None and index < 0:
        raise HTTPException(400, "index must be >= 0")
    try:
        ref = resolve_image_data_ref(item, index=index, meta=meta)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return build_storage_redirect_response(ref.nginx_path)


@router.get("/images/{image_id}/thumbnail")
async def get_public_image_thumbnail(
    image_id: str,
    size: int = 144,
    _: bool = Depends(is_authenticated),
    service: ImageInstanceService = Depends(get_image_instance_service),
):
    """Redirect to the stored thumbnail for an instance (by PublicID)."""
    item = service.get_for_storage(image_id)
    try:
        ref = resolve_thumbnail_ref(item, size=size)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return build_storage_redirect_response(ref.nginx_path)


@router.get("/instances/images/{dataset_identifier:path}")
async def get_file(
    dataset_identifier: str,
    _: bool = Depends(is_authenticated),
):
    # Set X-Accel-Redirect header to tell NGINX to serve the file
    response = Response()
    response.headers["X-Accel-Redirect"] = "/files/" + dataset_identifier
    return response


@router.get("/instances/thumbnails/{thumbnail_identifier:path}")
async def get_thumb(
    thumbnail_identifier: str,
    _: bool = Depends(is_authenticated),
):
    response = Response()
    response.headers["X-Accel-Redirect"] = "/thumbnails/" + thumbnail_identifier
    return response


@router.post("/instances/{instance_id}/tags", response_model=TagMeta)
async def tag_instance(
    instance_id: str,
    body: ObjectTagPOST,
    service: ImageInstanceService = Depends(get_image_instance_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Attach a Tag to an ImageInstance by tag ID (idempotent)."""
    link = service.tag_instance(
        instance_id,
        body.tag_id,
        body.comment,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.link_to_tag_metadata(link)


@router.patch("/instances/{instance_id}/tags/{tag_id}", response_model=TagMeta)
async def patch_instance_tag(
    instance_id: str,
    tag_id: int,
    body: ObjectTagPATCH,
    service: ImageInstanceService = Depends(get_image_instance_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Update comment on an existing ImageInstance tag link."""
    link = service.patch_instance_tag(
        instance_id,
        tag_id,
        body.comment,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.link_to_tag_metadata(link)


@router.delete("/instances/{instance_id}/tags/{tag_id}", status_code=204)
async def untag_instance(
    instance_id: str,
    tag_id: int,
    service: ImageInstanceService = Depends(get_image_instance_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove a Tag from an ImageInstance (idempotent)."""
    service.untag_instance(
        instance_id,
        tag_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)
