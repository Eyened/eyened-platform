

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, get_origin

from pydantic import BaseModel

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


# === TASK STATE ===
class TaskStateBase(BaseModel):
    name: str


class TaskStatePUT(TaskStateBase):
    pass


class TaskStateGET(TaskStateBase):
    id: int


# === TASK ===
class TaskBase(BaseModel):
    name: str
    description: Optional[str] = None
    contact_id: Optional[int] = None
    task_definition_id: int
    task_state_id: int


class TaskPUT(TaskBase):
    pass


class TaskGET(TaskBase):
    id: int
    date_inserted: datetime


# === SUB TASK ===
class SubTaskBase(BaseModel):
    task_id: int
    task_state_id: int
    creator_id: Optional[int] = None


class SubTaskPUT(SubTaskBase):
    pass


class SubTaskGET(SubTaskBase):
    id: int