from typing import Dict, List

from eyened_orm import (
    AnnotationType,
    Contact,
    CompositeFeature,
    Creator,
    DeviceInstance,
    DeviceModel,
    Feature,
    FormSchema,
    Project,
    Scan,
    Task,
    TaskDefinition,
    TaskState,
)
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from .auth import CurrentUser, get_current_user

router = APIRouter()


# Pydantic model for response validation
class DataResponse(BaseModel):
    features: List[Feature]
    creators: List[Creator]
    contacts: List[Contact]
    # annotation_types: List[AnnotationType] = Field(alias="annotation-types")
    composite_features: List[CompositeFeature] = Field(alias="composite-features")
    form_schemas: List[FormSchema] = Field(alias="form-schemas")
    task_definitions: List[TaskDefinition] = Field(alias="task-definitions")
    projects: List[Project]
    scans: List[Scan]
    devices: List[DeviceInstance]
    device_models: List[DeviceModel] = Field(alias="device-models")
    tasks: List[Task]
    task_states: List[TaskState] = Field(alias="task-states")

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True


@router.get("/data", response_model=DataResponse)
async def get_data(
    db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
):
    tables = {
        "features": Feature,
        "contacts": Contact,
        "creators": Creator,
        # "annotation-types": AnnotationType,
        "composite-features": CompositeFeature,
        "form-schemas": FormSchema,
        "task-definitions": TaskDefinition,
        "projects": Project,
        "scans": Scan,
        "devices": DeviceInstance,
        "device-models": DeviceModel,
        "tasks": Task,
        "task-states": TaskState,
    }

    return {
        table_name: [row.to_dict() for row in table.fetch_all(db)]
        for table_name, table in tables.items()
    }
