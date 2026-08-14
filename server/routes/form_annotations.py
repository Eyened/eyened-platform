from typing import List, Optional

from fastapi import APIRouter, Depends, Request, Response

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_aux import ObjectTagPATCH, ObjectTagPOST, TagMeta
from ..dtos.dtos_main import (
    FormAnnotationGET,
    FormAnnotationPATCH,
    FormAnnotationPUT,
)
from ..services.form_annotation_service import (
    FormAnnotationService,
    get_form_annotation_service,
)
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.post("/form-annotations", response_model=FormAnnotationGET)
async def create_form_annotation(
    annotation: FormAnnotationPUT,
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a form annotation."""
    item = service.create(
        **annotation.dict(),
    )
    return DTOConverter.form_annotation_to_get(item)


@router.get("/form-annotations", response_model=List[FormAnnotationGET])
async def get_form_annotations(
    patient_id: Optional[int] = None,
    study_id: Optional[int] = None,
    image_id: Optional[str] = None,
    form_schema_id: Optional[int] = None,
    sub_task_id: Optional[int] = None,
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List active form annotations, optionally filtered."""
    rows = service.list_annotations(
        patient_id=patient_id,
        study_id=study_id,
        image_id=image_id,
        form_schema_id=form_schema_id,
        sub_task_id=sub_task_id,
    )
    return [DTOConverter.form_annotation_to_get(row) for row in rows]


@router.get("/form-annotations/{annotation_id}", response_model=FormAnnotationGET)
async def get_form_annotation(
    annotation_id: int,
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single form annotation by id."""
    item = service.get_annotation(annotation_id)
    return DTOConverter.form_annotation_to_get(item)


@router.patch("/form-annotations/{annotation_id}", response_model=FormAnnotationGET)
async def update_form_annotation(
    annotation_id: int,
    annotation: FormAnnotationPATCH,
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Partially update a form annotation."""
    item = service.update(
        annotation_id,
        annotation.dict(exclude_unset=True),
    )
    return DTOConverter.form_annotation_to_get(item)


@router.delete("/form-annotations/{annotation_id}", status_code=204)
async def delete_form_annotation(
    annotation_id: int,
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Soft-delete a form annotation."""
    service.soft_delete(
        annotation_id,
    )
    return Response(status_code=204)


@router.get("/form-annotations/{form_annotation_id}/value")
async def get_form_annotation_value(
    form_annotation_id: int,
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a form annotation's raw FormData payload."""
    return service.get_value(form_annotation_id)


@router.put("/form-annotations/{form_annotation_id}/value", status_code=204)
async def update_form_annotation_value(
    form_annotation_id: int,
    request: Request,
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Overwrite a form annotation's FormData payload."""
    form_data = await request.json()
    service.set_value(
        form_annotation_id,
        form_data,
    )
    return Response(status_code=204)


@router.post("/form-annotations/{annotation_id}/tags", response_model=TagMeta)
async def tag_form_annotation(
    annotation_id: int,
    body: ObjectTagPOST,
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Attach a Tag to a FormAnnotation by tag ID (idempotent)."""
    link = service.tag(
        annotation_id,
        body.tag_id,
        body.comment,
    )
    return DTOConverter.link_to_tag_metadata(link)


@router.delete("/form-annotations/{annotation_id}/tags/{tag_id}", status_code=204)
async def untag_form_annotation(
    annotation_id: int,
    tag_id: int,
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove a Tag from a FormAnnotation (idempotent)."""
    service.untag(
        annotation_id,
        tag_id,
    )
    return Response(status_code=204)


@router.patch(
    "/form-annotations/{annotation_id}/tags/{tag_id}", response_model=TagMeta
)
async def patch_form_annotation_tag(
    annotation_id: int,
    tag_id: int,
    body: ObjectTagPATCH,
    service: FormAnnotationService = Depends(get_form_annotation_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Update comment on an existing FormAnnotation tag link."""
    link = service.patch_tag(
        annotation_id,
        tag_id,
        body.comment,
    )
    return DTOConverter.link_to_tag_metadata(link)
