from typing import Union, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session, selectinload
from pydantic import BaseModel
from eyened_orm import SubTask, SubTaskImageLink, ImageInstance
from ..db import get_db
from ..utils.db_logging import get_db_logger
from .auth import CurrentUser, get_current_user
from ..dtos.dtos_tasks import (
    SubTasksResponse,
    SubTasksWithImagesResponse,
    SubTaskGET,
    SubTaskWithImagesGET,
)
from ..dtos.dtos_instances import ImageGET
from ..dtos.dto_converter import DTOConverter

router = APIRouter()


class SubTaskPATCH(BaseModel):
    comments: Optional[str] = None
    task_state: Optional[str] = None  # align with TaskState enum names


class AddImageRequest(BaseModel):
    instance_id: str


def _resolve_image_instance_id(db: Session, image_id: str) -> int:
    item = (
        db.query(ImageInstance)
        .filter(ImageInstance.PublicID == image_id)
        .first()
    )
    if item:
        return item.ImageInstanceID
    raise HTTPException(status_code=404, detail="ImageInstance not found")


@router.get(
    "/subtasks/{subtaskid}", response_model=Union[SubTaskWithImagesGET, SubTaskGET]
)
async def get_subtask(
    subtaskid: int,
    with_images: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    q = select(SubTask).where(SubTask.SubTaskID == subtaskid)
    if with_images:
        q = q.options(
            selectinload(SubTask.SubTaskImageLinks).selectinload(
                SubTaskImageLink.ImageInstance
            )
        )
    st = db.execute(q).scalars().first()
    if not st:
        raise HTTPException(404, "SubTask not found")
    if with_images:
        return DTOConverter.subtask_with_images_to_get(st)
    return DTOConverter.subtask_to_get(st)


@router.patch("/subtasks/{subtaskid}", response_model=SubTaskGET)
async def patch_subtask(
    subtaskid: int,
    dto: SubTaskPATCH,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    st = db.get(SubTask, subtaskid)
    if not st:
        raise HTTPException(404, "SubTask not found")
    changes = {}
    if dto.comments is not None:
        changes["comments"] = f"{st.Comments} -> {dto.comments}"
        st.Comments = dto.comments
    if dto.task_state is not None:
        changes["task_state"] = f"{st.TaskState} -> {dto.task_state}"
        st.TaskState = dto.task_state
    db.commit()
    db.refresh(st)

    # Log subtask update
    logger = get_db_logger()
    if logger:
        logger.log_update(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"PATCH /api/subtasks/{subtaskid}",
            entity="SubTask",
            entity_id=subtaskid,
            changes=changes if changes else None,
        )

    return DTOConverter.subtask_to_get(st)


@router.delete("/subtasks/{subtaskid}", status_code=204)
async def delete_subtask(
    subtaskid: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    # Get subtask data before deletion
    st = db.get(SubTask, subtaskid)
    if not st:
        raise HTTPException(404, "SubTask not found")

    # Save subtask data for logging before deletion
    deleted_data = {
        "task_id": st.TaskID,
        "comments": st.Comments,
        "task_state": str(st.TaskState) if st.TaskState else None,
        "creator_id": st.CreatorID,
    }

    res = db.execute(delete(SubTask).where(SubTask.SubTaskID == subtaskid))
    if res.rowcount == 0:
        raise HTTPException(404, "SubTask not found")
    db.commit()

    # Log subtask deletion
    logger = get_db_logger()
    if logger:
        logger.log_delete(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"DELETE /api/subtasks/{subtaskid}",
            entity="SubTask",
            entity_id=subtaskid,
            deleted_data=deleted_data,
        )

    return Response(status_code=204)


@router.post("/subtasks/{subtaskid}/images", response_model=SubTaskWithImagesGET)
async def add_subtask_image(
    subtaskid: int,
    body: AddImageRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    st = db.get(SubTask, subtaskid)
    if not st:
        raise HTTPException(404, "SubTask not found")
    image_instance_id = _resolve_image_instance_id(db, body.instance_id)
    inst = db.get(ImageInstance, image_instance_id)
    if not inst:
        raise HTTPException(404, "ImageInstance not found")
    # Get the next available ImageIndex for this subtask
    max_index = db.scalar(
        select(func.max(SubTaskImageLink.ImageIndex)).where(
            SubTaskImageLink.SubTaskID == subtaskid
        )
    )
    if max_index is None:
        max_index = -1
    link = SubTaskImageLink(
        SubTaskID=subtaskid,
        ImageInstanceID=image_instance_id,
        ImageIndex=max_index + 1,
    )

    try:
        db.add(link)
        db.commit()
    except Exception as e:
        print("Error adding image link:", e)
        print(e)
        db.rollback()
        raise HTTPException(500, "Error adding image link")

    # Log image link creation
    logger = get_db_logger()
    if logger:
        logger.log_insert(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"POST /api/subtasks/{subtaskid}/images",
            entity="SubTaskImageLink",
            fields={
                "subtask_id": subtaskid,
                "image_instance_id": image_instance_id,
            },
        )

    # Fetch the updated subtask with images
    st = (
        db.execute(
            select(SubTask)
            .where(SubTask.SubTaskID == subtaskid)
            .options(
                selectinload(SubTask.SubTaskImageLinks).selectinload(
                    SubTaskImageLink.ImageInstance
                )
            )
        )
        .scalars()
        .first()
    )
    return DTOConverter.subtask_with_images_to_get(st)


@router.delete(
    "/subtasks/{subtaskid}/images/{instance_id}", response_model=SubTaskWithImagesGET
)
async def remove_subtask_image(
    subtaskid: int,
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    # Get link data before deletion (for logging)
    image_instance_id = _resolve_image_instance_id(db, instance_id)
    link = db.get(
        SubTaskImageLink, {"SubTaskID": subtaskid, "ImageInstanceID": image_instance_id}
    )
    if not link:
        raise HTTPException(404, "Link not found")

    deleted_data = {
        "subtask_id": subtaskid,
        "image_instance_id": image_instance_id,
    }

    res = db.execute(
        delete(SubTaskImageLink).where(
            SubTaskImageLink.SubTaskID == subtaskid,
            SubTaskImageLink.ImageInstanceID == image_instance_id,
        )
    )
    if res.rowcount == 0:
        raise HTTPException(404, "Link not found")
    db.commit()

    # Log image link deletion
    logger = get_db_logger()
    if logger:
        logger.log_delete(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"DELETE /api/subtasks/{subtaskid}/images/{instance_id}",
            entity="SubTaskImageLink",
            fields=deleted_data,
            deleted_data=deleted_data,
        )

    # Fetch the updated subtask with images
    st = (
        db.execute(
            select(SubTask)
            .where(SubTask.SubTaskID == subtaskid)
            .options(
                selectinload(SubTask.SubTaskImageLinks).selectinload(
                    SubTaskImageLink.ImageInstance
                )
            )
        )
        .scalars()
        .first()
    )
    return DTOConverter.subtask_with_images_to_get(st)
