from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from eyened_orm import Task
from ..db import get_db
from .auth import CurrentUser, get_current_user
from ..dtos.dtos_tasks import TaskPUT, TaskPATCH, TaskGET
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
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    db.delete(task); db.commit()
    return Response(status_code=204)
