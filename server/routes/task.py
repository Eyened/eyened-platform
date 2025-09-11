from typing import Union, List
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session, selectinload
from eyened_orm import Task, SubTask, SubTaskImageLink, ImageInstance
from ..db import get_db
from .auth import CurrentUser, get_current_user
from ..dtos.dtos_tasks import (
    TaskPUT, TaskPATCH, TaskGET,
    SubTasksResponse, SubTasksWithImagesResponse,
    SubTaskGET, SubTaskWithImagesGET,
)
from ..dtos.dto_converter import DTOConverter

router = APIRouter()

@router.post("/task", response_model=TaskGET)
async def create_task(dto: TaskPUT, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    task = Task(
        TaskName=dto.name,
        Description=dto.description,
        ContactID=dto.contact_id,
        TaskDefinitionID=dto.task_definition_id,
        TaskStateID=dto.task_state_id,
    )
    db.add(task); db.commit(); db.refresh(task)
    return DTOConverter.task_to_get(task)

@router.get("/task/{task_id}", response_model=TaskGET)
async def get_task(task_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return DTOConverter.task_to_get(task)

@router.patch("/task/{task_id}", response_model=TaskGET)
async def patch_task(task_id: int, dto: TaskPATCH, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    payload = dto.model_dump()
    task.TaskName = payload.get("name", task.TaskName)
    task.Description = payload.get("description", task.Description)
    task.ContactID = payload.get("contact_id", task.ContactID)
    task.TaskDefinitionID = payload.get("task_definition_id", task.TaskDefinitionID)
    task.TaskStateID = payload.get("task_state_id", task.TaskStateID)
    db.commit(); db.refresh(task)
    return DTOConverter.task_to_get(task)

@router.delete("/task/{task_id}", status_code=204)
async def delete_task(task_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    res = db.execute(delete(Task).where(Task.TaskID == task_id))
    if res.rowcount == 0:
        raise HTTPException(404, "Task not found")
    db.commit()
    return Response(status_code=204)


@router.get("/task", response_model=List[TaskGET])
async def list_tasks(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all tasks (no pagination)."""
    rows = db.execute(select(Task).order_by(Task.TaskID)).scalars().all()
    return [DTOConverter.task_to_get(t) for t in rows]


@router.get(
    "/task/{task_id}/subtasks",
    response_model=Union[SubTasksWithImagesResponse,SubTasksResponse],
)
async def list_subtasks(
    task_id: int,
    with_images: bool = False,
    limit: int = 200,
    page: int = 0,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List subtasks of a task with optional pagination and image inclusion."""
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    offset = limit * page
    q = (
        select(SubTask)
        .where(SubTask.TaskID == task_id)
        .order_by(SubTask.SubTaskID)
    )
    if with_images:
        q = q.options(
            selectinload(SubTask.SubTaskImageLinks).selectinload(SubTaskImageLink.ImageInstance)
        )

    rows = db.execute(q.limit(limit).offset(offset)).scalars().all()
    count = db.scalar(select(func.count()).select_from(SubTask).where(SubTask.TaskID == task_id)) or 0

    if with_images:
        subtasks = [DTOConverter.subtask_with_images_to_get(st) for st in rows]
        return {"subtasks": subtasks, "limit": limit, "page": page, "count": count}

    subtasks = [DTOConverter.subtask_to_get(st) for st in rows]
    return {"subtasks": subtasks, "limit": limit, "page": page, "count": count}


@router.get(
    "/task/{task_id}/subtask/{subtaskid}",
    response_model=Union[SubTaskWithImagesGET,SubTaskGET],
)
async def get_subtask(
    task_id: int,
    subtaskid: int,
    with_images: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single subtask with optional image inclusion."""
    q = select(SubTask).where(SubTask.SubTaskID == subtaskid, SubTask.TaskID == task_id)
    if with_images:
        q = q.options(
            selectinload(SubTask.SubTaskImageLinks).selectinload(SubTaskImageLink.ImageInstance)
        )
    subtask = db.execute(q).scalars().first()
    if not subtask:
        raise HTTPException(404, "SubTask not found")

    if with_images:
        return DTOConverter.subtask_with_images_to_get(subtask)
    return DTOConverter.subtask_to_get(subtask)


@router.delete("/task/{task_id}/subtask/{subtaskid}", status_code=204)
async def delete_subtask(task_id: int, subtaskid: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    res = db.execute(delete(SubTask).where(SubTask.SubTaskID == subtaskid, SubTask.TaskID == task_id))
    if res.rowcount == 0:
        raise HTTPException(404, "SubTask not found")
    db.commit()
    return Response(status_code=204)
