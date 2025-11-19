from typing import Union, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session, selectinload
from pydantic import BaseModel
from eyened_orm import SubTask, SubTaskImageLink, ImageInstance
from ..db import get_db
from .auth import CurrentUser, get_current_user
from ..dtos.dtos_tasks import (
    SubTasksResponse, SubTasksWithImagesResponse,
    SubTaskGET, SubTaskWithImagesGET,
)
from ..dtos.dtos_instances import InstanceGET
from ..dtos.dto_converter import DTOConverter

router = APIRouter()

class SubTaskPATCH(BaseModel):
    comments: Optional[str] = None
    task_state: Optional[str] = None  # align with TaskState enum names

class AddImageRequest(BaseModel):
    instance_id: int


@router.get("/subtasks/{subtaskid}", response_model=Union[SubTaskWithImagesGET, SubTaskGET])
async def get_subtask(
    subtaskid: int,
    with_images: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    q = select(SubTask).where(SubTask.SubTaskID == subtaskid)
    if with_images:
        q = q.options(
            selectinload(SubTask.SubTaskImageLinks).selectinload(SubTaskImageLink.ImageInstance)
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
    if dto.comments is not None:
        st.Comments = dto.comments
    if dto.task_state is not None:
        st.TaskState = dto.task_state
    db.commit(); db.refresh(st)
    return DTOConverter.subtask_to_get(st)

@router.delete("/subtasks/{subtaskid}", status_code=204)
async def delete_subtask(
    subtaskid: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    res = db.execute(delete(SubTask).where(SubTask.SubTaskID == subtaskid))
    if res.rowcount == 0:
        raise HTTPException(404, "SubTask not found")
    db.commit()
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
    inst = db.get(ImageInstance, body.instance_id)
    if not inst:
        raise HTTPException(404, "ImageInstance not found")
    link = SubTaskImageLink(SubTaskID=subtaskid, ImageInstanceID=body.instance_id)
    db.add(link); db.commit()
    
    # Fetch the updated subtask with images
    st = db.execute(
        select(SubTask)
        .where(SubTask.SubTaskID == subtaskid)
        .options(selectinload(SubTask.SubTaskImageLinks).selectinload(SubTaskImageLink.ImageInstance))
    ).scalars().first()
    return DTOConverter.subtask_with_images_to_get(st)

@router.delete("/subtasks/{subtaskid}/images/{instance_id}", response_model=SubTaskWithImagesGET)
async def remove_subtask_image(
    subtaskid: int,
    instance_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    res = db.execute(
        delete(SubTaskImageLink).where(
            SubTaskImageLink.SubTaskID == subtaskid,
            SubTaskImageLink.ImageInstanceID == instance_id
        )
    )
    if res.rowcount == 0:
        raise HTTPException(404, "Link not found")
    db.commit()
    
    # Fetch the updated subtask with images
    st = db.execute(
        select(SubTask)
        .where(SubTask.SubTaskID == subtaskid)
        .options(selectinload(SubTask.SubTaskImageLinks).selectinload(SubTaskImageLink.ImageInstance))
    ).scalars().first()
    return DTOConverter.subtask_with_images_to_get(st)
