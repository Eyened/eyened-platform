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
        CreatorID=current_user.id,
    )
    db.add(task); db.commit(); db.refresh(task)
    return DTOConverter.task_to_get(task)

@router.get("/task", response_model=List[TaskGET])
async def list_tasks(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all tasks (no pagination)."""
    rows = db.execute(
        select(Task)
        .options(selectinload(Task.SubTasks), selectinload(Task.Creator))
        .order_by(Task.TaskID)
    ).scalars().all()
    return [DTOConverter.task_to_get(t) for t in rows]

@router.get("/task/{task_id}", response_model=TaskGET)
async def get_task(task_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    task = db.execute(
        select(Task)
        .options(selectinload(Task.SubTasks), selectinload(Task.Creator))
        .where(Task.TaskID == task_id)
    ).scalars().first()
    if not task:
        raise HTTPException(404, "Task not found")
    return DTOConverter.task_to_get(task)

@router.patch("/task/{task_id}", response_model=TaskGET)
async def patch_task(task_id: int, dto: TaskPATCH, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if dto.name is not None:
        task.TaskName = dto.name
    if dto.description is not None:
        task.Description = dto.description
    if dto.contact_id is not None:
        task.ContactID = dto.contact_id
    if dto.task_definition_id is not None:
        task.TaskDefinitionID = dto.task_definition_id
    if dto.task_state is not None:
        task.TaskState = dto.task_state

    db.commit(); db.refresh(task)
    
    # Reload with SubTasks for consistency
    task = db.execute(
        select(Task)
        .options(selectinload(Task.SubTasks), selectinload(Task.Creator))
        .where(Task.TaskID == task_id)
    ).scalars().first()
    
    return DTOConverter.task_to_get(task)

@router.delete("/task/{task_id}", status_code=204)
async def delete_task(task_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    res = db.execute(delete(Task).where(Task.TaskID == task_id))
    if res.rowcount == 0:
        raise HTTPException(404, "Task not found")
    db.commit()
    return Response(status_code=204)





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
        subtasks = [
            DTOConverter.subtask_with_images_to_get(st).copy(update={'index': offset + i})
            for i, st in enumerate(rows)
        ]
        return {"subtasks": subtasks, "limit": limit, "page": page, "count": count}

    subtasks = [
        DTOConverter.subtask_to_get(st).copy(update={'index': offset + i})
        for i, st in enumerate(rows)
    ]
    return {"subtasks": subtasks, "limit": limit, "page": page, "count": count}



@router.get(
    "/task/{task_id}/subtask/{subtask_index}",
    response_model=Union[SubTaskWithImagesGET, SubTaskGET],
)
async def get_subtask(
    task_id: int,
    subtask_index: int,
    with_images: bool = False,
    with_next: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single subtask by index with optional image inclusion and next task."""
    base_q = select(SubTask).where(SubTask.TaskID == task_id).order_by(SubTask.SubTaskID)
    if with_images:
        base_q = base_q.options(
            selectinload(SubTask.SubTaskImageLinks).selectinload(SubTaskImageLink.ImageInstance)
        )
    q = base_q.offset(subtask_index).limit(2 if with_next else 1)
    rows = db.execute(q).scalars().all()
    if not rows:
        raise HTTPException(404, "SubTask not found")

    main = rows[0]
    main_dto = (
        DTOConverter.subtask_with_images_to_get(main)
        if with_images else DTOConverter.subtask_to_get(main)
    ).copy(update={'index': subtask_index})

    if with_next and len(rows) > 1:
        nxt = rows[1]
        next_dto = (
            DTOConverter.subtask_with_images_to_get(nxt)
            if with_images else DTOConverter.subtask_to_get(nxt)
        ).copy(update={'index': subtask_index + 1})
        main_dto = main_dto.copy(update={'next_task': next_dto})

    return main_dto

