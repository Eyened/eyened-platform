from typing import Optional, Union

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from eyened_orm.task import SubTaskState

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_tasks import SubTaskGET, SubTaskWithImagesGET
from ..services.acting_user import ActingUser
from ..services.task_service import SubTaskService, get_subtask_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


class SubTaskPATCH(BaseModel):
    comments: Optional[str] = None
    task_state: Optional[SubTaskState] = None
    claim: Optional[bool] = None


class AddImageRequest(BaseModel):
    instance_id: str


@router.get(
    "/subtasks/{subtaskid}", response_model=Union[SubTaskWithImagesGET, SubTaskGET]
)
async def get_subtask(
    subtaskid: int,
    with_images: bool = False,
    db: Session = Depends(get_db),
    service: SubTaskService = Depends(get_subtask_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single subtask, optionally with its images."""
    st = service.get_subtask(db, subtaskid, with_images=with_images)
    if with_images:
        return DTOConverter.subtask_with_images_to_get(st)
    return DTOConverter.subtask_to_get(st)


@router.patch("/subtasks/{subtaskid}", response_model=SubTaskGET)
async def patch_subtask(
    subtaskid: int,
    dto: SubTaskPATCH,
    db: Session = Depends(get_db),
    service: SubTaskService = Depends(get_subtask_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a subtask's comments and/or state."""
    st = service.update_subtask(
        db,
        subtaskid,
        dto.comments,
        dto.task_state,
        ActingUser(id=current_user.id, username=current_user.username),
        claim=dto.claim,
    )
    return DTOConverter.subtask_to_get(st)


@router.delete("/subtasks/{subtaskid}", status_code=204)
async def delete_subtask(
    subtaskid: int,
    db: Session = Depends(get_db),
    service: SubTaskService = Depends(get_subtask_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a subtask."""
    service.delete_subtask(
        db,
        subtaskid,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)


@router.post("/subtasks/{subtaskid}/images", response_model=SubTaskWithImagesGET)
async def add_subtask_image(
    subtaskid: int,
    body: AddImageRequest,
    db: Session = Depends(get_db),
    service: SubTaskService = Depends(get_subtask_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Link an image to a subtask at the next available index."""
    st = service.add_image(
        db,
        subtaskid,
        body.instance_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.subtask_with_images_to_get(st)


@router.delete(
    "/subtasks/{subtaskid}/images/{instance_id}", response_model=SubTaskWithImagesGET
)
async def remove_subtask_image(
    subtaskid: int,
    instance_id: str,
    db: Session = Depends(get_db),
    service: SubTaskService = Depends(get_subtask_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Unlink an image from a subtask."""
    st = service.remove_image(
        db,
        subtaskid,
        instance_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.subtask_with_images_to_get(st)
