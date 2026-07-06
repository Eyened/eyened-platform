

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, get_origin

from pydantic import BaseModel
from eyened_orm import TaskState, SubTaskState

from .dtos_instances import ImageGET
from .dtos_aux import CreatorMeta

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= TASK SYSTEM=========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class TaskDefinitionBase(BaseModel):
    name: str


class TaskDefinitionPUT(TaskDefinitionBase):
    pass


class TaskDefinitionGET(TaskDefinitionBase):
    id: int
    config: Dict[str, Any]
    date_inserted: datetime


# === TASK ===
class TaskBase(BaseModel):
    name: str
    description: Optional[str] = None
    contact_id: Optional[int] = None
    task_definition_id: int

class TaskPUT(TaskBase):
    pass


class TaskPATCH(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    contact_id: Optional[int] = None
    task_definition_id: Optional[int] = None
    task_state: Optional[TaskState] = None


class TaskGET(TaskBase):
    id: int
    date_inserted: datetime
    num_tasks: int
    num_tasks_ready: int
    creator: Optional[CreatorMeta] = None
    task_state: Optional[TaskState] = None
    task_definition: TaskDefinitionGET


# === SUB TASK ===
class SubTaskBase(BaseModel):
    task_id: int
    task_state: SubTaskState
    comments: Optional[str] = None

class SubTaskPOST(BaseModel):
    comments: Optional[str] = None

class SubTaskPUT(SubTaskBase):
    pass


class SubTaskGET(SubTaskBase):
    id: int
    creator_id: Optional[int] = None
    # New optional metadata
    index: Optional[int] = None
    next_task: Optional["SubTaskGET"] = None


class SubTaskWithImagesGET(SubTaskGET):
    """SubTask with associated images included."""
    images: List[ImageGET]


class SubTasksResponse(BaseModel):
    """Response envelope for paginated SubTasks without images."""
    subtasks: List[SubTaskGET]
    limit: int
    page: int
    count: int


class SubTasksWithImagesResponse(BaseModel):
    """Response envelope for paginated SubTasks with images."""
    subtasks: List[SubTaskWithImagesGET]
    limit: int
    page: int
    count: int