from typing import Dict, List

from eyened_orm import (AnnotationType, Creator, DeviceInstance, DeviceModel,
                        Feature, FormSchema, Project, Scan, Task,
                        TaskDefinition, TaskState)
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth import manager
from .db import get_db

router = APIRouter()


# Pydantic model for response validation
class DataResponse(BaseModel):
    features: List[Dict]
    creators: List[Dict]
    annotationTypes: List[Dict]
    formSchemas: List[Dict]
    taskDefinitions: List[Dict]
    projects: List[Dict]
    scans: List[Dict]
    devices: List[Dict]
    deviceModels: List[Dict]
    tasks: List[Dict]
    taskStates: List[Dict]

    class Config:
        arbitrary_types_allowed = True


@router.get("/data", response_model=DataResponse)
async def get_data(
    db: Session = Depends(get_db),
    user_id: int = Depends(manager)
):
    tables = {
        "features": Feature,
        "creators": Creator,
        "annotationTypes": AnnotationType,
        "formSchemas": FormSchema,
        "taskDefinitions": TaskDefinition,
        "projects": Project,
        "scans": Scan,
        "devices": DeviceInstance,
        "deviceModels": DeviceModel,
        "tasks": Task,
        "taskStates": TaskState,
    }

    return {
        table_name: [row.to_dict() for row in table.fetch_all(db)]
        for table_name, table in tables.items()
    }
