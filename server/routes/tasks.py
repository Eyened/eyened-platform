from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Response, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from eyened_orm import (
    SubTask,
    SubTaskImageLink,
    Task,
    TaskDefinition,
    TaskState,
)

from .auth import manager
from .db import get_db

router = APIRouter()

class SubTaskImageLinkCreate(BaseModel):
    SubTaskID: int
    ImageInstanceID: int

class TaskDefinitionCreate(BaseModel):
    TaskDefinitionName: str

class TaskCreate(BaseModel):
    TaskName: str
    TaskDefinitionID: int

class TaskStateUpdate(BaseModel):
    state: str

class TaskResponse(BaseModel):
    TaskID: int
    TaskName: str
    size: int

@router.get("/tasks/{taskid}/subtasks")
async def get_subtasks(
    taskid: int, db: Session = Depends(get_db),
    user_id: int = Depends(manager)
):
    result = (db.query(SubTask).join(Task).filter(Task.TaskID == taskid)).all()
    links = (
        db.query(SubTaskImageLink).join(
            SubTask).filter(SubTask.TaskID == taskid)
    ).all()

    return {
        "subTasks": [r.to_dict() for r in result],
        "subTaskImageLinks": [r.to_dict() for r in links],
    }


@router.put("/subtasks/{SubTaskID}/taskstateid")
async def update_task_state_id(
    SubTaskID: int,
    state_id: int = Body(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(manager),
):
    subtask = db.get(SubTask, SubTaskID)
    if not subtask:
        raise HTTPException(status_code=404, detail="SubTask not found")

    subtask.TaskStateID = state_id
    db.commit()
    return Response(status_code=204)


@router.post("/subTaskImageLinks/new", response_model=Dict)
async def create_subtask_image_link(
    link_data: SubTaskImageLinkCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(manager),
):
    link = SubTaskImageLink(
        SubTaskID=link_data.SubTaskID, ImageInstanceID=link_data.ImageInstanceID
    )
    db.add(link)
    db.commit()
    return link.to_dict()


@router.delete("/subTaskImageLinks/{link_id}")
async def delete_subtask_image_link(
    link_id: int, db: Session = Depends(get_db),
    user_id: int = Depends(manager)
):
    link = db.get(SubTaskImageLink, link_id)
    if not link:
        raise HTTPException(
            status_code=404, detail="SubTaskImageLink not found")

    db.delete(link)
    db.commit()
    return Response(status_code=204)


@router.post("/taskDefinitions/new", response_model=Dict)
async def create_task_definition(
    task_def: TaskDefinitionCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(manager)
):
    taskdefinition = TaskDefinition(TaskDefinitionName=task_def.TaskDefinitionName)
    db.add(taskdefinition)
    db.commit()
    return taskdefinition.to_dict()


@router.post("/tasks/new", response_model=Dict)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(manager)
):
    taskdef = db.get(TaskDefinition, task_data.TaskDefinitionID)
    if not taskdef:
        raise HTTPException(status_code=404, detail="TaskDefinition not found")

    newtask = Task(TaskName=task_data.TaskName, TaskDefinition=taskdef)
    db.add(newtask)
    db.commit()
    return newtask.to_dict()


@router.get("/tasks/{taskid}")
async def get_task(
    taskid: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(manager)
):
    task = db.get(Task, taskid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    columns = Task.column_names + ["size"]
    data = task.to_list() + [len(task.SubTasks)]
    return dict(zip(columns, data))


@router.delete("/tasks/{taskid}")
async def delete_task(
    taskid: int, 
    db: Session = Depends(get_db), 
    user_id: int = Depends(manager)
):
    task = db.get(Task, taskid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return Response(status_code=204)


@router.get("/tasks/{taskid}/subtasks/{index}")
async def get_subtask_from_task(
    taskid: int,
    index: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(manager)
):
    task = db.get(Task, taskid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        subtask = task.SubTasks[index]
        return subtask.to_dict(with_images=True)
    except IndexError:
        raise HTTPException(
            status_code=404, detail="SubTask index out of range")


@router.put("/subtasks/{subtaskid}/state")
async def update_subtask_state(
    subtaskid: int,
    state_data: TaskStateUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(manager)
):
    subtask = db.get(SubTask, subtaskid)
    if not subtask:
        raise HTTPException(status_code=404, detail="SubTask not found")

    taskstate = TaskState.by_name(db, state_data.state)
    if not taskstate:
        taskstate = TaskState(TaskStateName=state_data.state)

    subtask.TaskState = taskstate
    db.commit()
    return subtask.to_dict()
