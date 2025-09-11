

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, get_origin

from pydantic import BaseModel
from eyened_orm import TaskState

from .dtos_instances import InstanceGET

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= TASK SYSTEM=========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class TaskDefinitionBase(BaseModel):
    name: str


class TaskDefinitionPUT(TaskDefinitionBase):
    pass


class TaskDefinitionGET(TaskDefinitionBase):
    id: int
    date_inserted: datetime


# === TASK ===
class TaskBase(BaseModel):
    name: str
    description: Optional[str] = None
    contact_id: Optional[int] = None
    task_definition_id: int


class TaskPUT(TaskBase):
    pass


class TaskPATCH(TaskPUT):
    """Partial update for Task (same fields as PUT for now)."""
    pass


class TaskGET(TaskBase):
    id: int
    date_inserted: datetime


# === SUB TASK ===
class SubTaskBase(BaseModel):
    task_id: int
    task_state: TaskState
    comments: Optional[str] = None


class SubTaskPUT(SubTaskBase):
    pass


class SubTaskGET(SubTaskBase):
    id: int
    creator_id: Optional[int] = None


class SubTaskWithImagesGET(SubTaskGET):
    """SubTask with associated images included."""
    images: List[InstanceGET]


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