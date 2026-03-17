from typing import Union, List, Optional
import bisect
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session, selectinload
from eyened_orm import (
    Task,
    SubTask,
    SubTaskImageLink,
    ImageInstance,
    ImageStorage,
    SubTaskState,
)
from ..db import get_db
from ..utils.db_logging import get_db_logger
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
    db.add(task); db.commit()
    # Reload with relationships
    task = db.execute(
        select(Task)
        .options(selectinload(Task.SubTasks), selectinload(Task.Creator), selectinload(Task.TaskDefinition))
        .where(Task.TaskID == task.TaskID)
    ).scalars().first()
    
    # Log task creation
    logger = get_db_logger()
    if logger:
        logger.log_insert(
            user=current_user.username,
            user_id=current_user.id,
            endpoint="POST /api/task",
            entity="Task",
            entity_id=task.TaskID,
            fields={
                "name": task.TaskName,
                "description": task.Description,
                "contact_id": task.ContactID,
                "task_definition_id": task.TaskDefinitionID,
            },
        )
    
    return DTOConverter.task_to_get(task)



@router.get("/task", response_model=List[TaskGET])
async def list_tasks(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all tasks (no pagination)."""
    rows = db.execute(
        select(Task)
        .options(selectinload(Task.SubTasks), selectinload(Task.Creator), selectinload(Task.TaskDefinition))
        .order_by(Task.TaskID)
    ).scalars().all()
    return [DTOConverter.task_to_get(t) for t in rows]




@router.get("/task/{task_id}", response_model=TaskGET)
async def get_task(task_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    task = db.execute(
        select(Task)
        .options(selectinload(Task.SubTasks), selectinload(Task.Creator), selectinload(Task.TaskDefinition))
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
    changes = {}
    if dto.name is not None:
        changes["name"] = f"{task.TaskName} -> {dto.name}"
        task.TaskName = dto.name
    if dto.description is not None:
        changes["description"] = f"{task.Description} -> {dto.description}"
        task.Description = dto.description
    if dto.contact_id is not None:
        changes["contact_id"] = f"{task.ContactID} -> {dto.contact_id}"
        task.ContactID = dto.contact_id
    if dto.task_definition_id is not None:
        changes["task_definition_id"] = f"{task.TaskDefinitionID} -> {dto.task_definition_id}"
        task.TaskDefinitionID = dto.task_definition_id
    if dto.task_state is not None:
        changes["task_state"] = f"{task.TaskState} -> {dto.task_state}"
        task.TaskState = dto.task_state

    db.commit(); db.refresh(task)
    
    # Reload with SubTasks for consistency
    task = db.execute(
        select(Task)
        .options(selectinload(Task.SubTasks), selectinload(Task.Creator), selectinload(Task.TaskDefinition))
        .where(Task.TaskID == task_id)
    ).scalars().first()
    
    # Log task update
    logger = get_db_logger()
    if logger:
        logger.log_update(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"PATCH /api/task/{task_id}",
            entity="Task",
            entity_id=task_id,
            changes=changes if changes else None,
        )
    
    return DTOConverter.task_to_get(task)

@router.delete("/task/{task_id}", status_code=204)
async def delete_task(task_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    # Get task data before deletion
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    
    # Save task data for logging before deletion
    deleted_data = {
        "name": task.TaskName,
        "description": task.Description,
        "contact_id": task.ContactID,
        "task_definition_id": task.TaskDefinitionID,
        "creator_id": task.CreatorID,
        "task_state": str(task.TaskState) if hasattr(task, 'TaskState') and task.TaskState else None,
    }
    
    res = db.execute(delete(Task).where(Task.TaskID == task_id))
    if res.rowcount == 0:
        raise HTTPException(404, "Task not found")
    db.commit()
    
    # Log task deletion
    logger = get_db_logger()
    if logger:
        logger.log_delete(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"DELETE /api/task/{task_id}",
            entity="Task",
            entity_id=task_id,
            deleted_data=deleted_data,
        )
    
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
    subtask_status: Optional[SubTaskState] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List subtasks of a task with optional pagination, image inclusion, and status filter.
    
    index is the 0-based position within all subtasks for the task ordered by SubTaskID 
    (computed before any subtask_status filtering).
    """
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    # Build absolute index map across all subtasks (before any status filtering)
    all_ids = db.execute(
        select(SubTask.SubTaskID)
        .where(SubTask.TaskID == task_id)
        .order_by(SubTask.SubTaskID)
    ).scalars().all()
    id_to_abs_idx = {sid: i for i, sid in enumerate(all_ids)}
    
    def abs_index_for(sid: int) -> int:
        i = id_to_abs_idx.get(sid)
        if i is not None:
            return i
        i = bisect.bisect_left(all_ids, sid)
        id_to_abs_idx[sid] = i
        return i

    offset = limit * page
    base_q = select(SubTask).where(SubTask.TaskID == task_id)
    if subtask_status is not None:
        base_q = base_q.where(SubTask.TaskState == subtask_status)

    q = base_q.order_by(SubTask.SubTaskID)
    if with_images:
        q = q.options(
            selectinload(SubTask.SubTaskImageLinks)
            .selectinload(SubTaskImageLink.ImageInstance)
            .selectinload(ImageInstance.ImageStorages)
            .selectinload(ImageStorage.StorageBackend)
        )

    rows = db.execute(q.limit(limit).offset(offset)).scalars().all()

    count_q = select(func.count()).select_from(SubTask).where(SubTask.TaskID == task_id)
    if subtask_status is not None:
        count_q = count_q.where(SubTask.TaskState == subtask_status)
    count = db.scalar(count_q) or 0

    if with_images:
        subtasks = [
            DTOConverter.subtask_with_images_to_get(st).copy(update={'index': abs_index_for(st.SubTaskID)})
            for st in rows
        ]
        return {"subtasks": subtasks, "limit": limit, "page": page, "count": count}

    subtasks = [
        DTOConverter.subtask_to_get(st).copy(update={'index': abs_index_for(st.SubTaskID)})
        for st in rows
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
            selectinload(SubTask.SubTaskImageLinks)
            .selectinload(SubTaskImageLink.ImageInstance)
            .selectinload(ImageInstance.ImageStorages)
            .selectinload(ImageStorage.StorageBackend)
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

