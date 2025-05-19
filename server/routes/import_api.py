from typing import Dict, Optional, Any, Union
import traceback
import datetime

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasic
from pydantic import BaseModel, Field
from server.routes.auth import CurrentUser, get_current_user
from sqlalchemy.orm import Session

from eyened_orm.importer.importer import Importer
from ..db import get_db
from ..config import settings
from ..utils.huey import task_run_inference, task_update_thumbnails

router = APIRouter()
security = HTTPBasic()


# Pydantic models for request and response schemas
class ImageImportData(BaseModel):
    """
    Model for a single image import data
    """

    project_name: str = Field(..., description="Required project name")
    patient_identifier: Optional[str] = Field(
        None, description="Patient identifier in the system"
    )
    patient_props: Optional[Dict[str, Any]] = Field(
        {}, description="Optional key-value properties for new patient"
    )
    study_date: Optional[Union[datetime.date, str]] = Field(
        None, description="Study date (can be a date object or ISO format string)"
    )
    study_props: Optional[Dict[str, Any]] = Field(
        {}, description="Optional key-value properties for new study"
    )
    series_id: Optional[str] = Field(None, description="Optional series identifier")
    series_props: Optional[Dict[str, Any]] = Field(
        {}, description="Optional key-value properties for new series"
    )
    image: str = Field(..., description="Path to the image file (required)")
    image_props: Optional[Dict[str, Any]] = Field(
        {}, description="Optional key-value properties for new image"
    )


class ImportOptions(BaseModel):
    """
    Options for the import process
    """

    create_patients: bool = Field(
        False, description="If True, create patients when they don't exist"
    )
    create_studies: bool = Field(
        False, description="If True, create studies when they don't exist"
    )
    create_series: bool = Field(
        True, description="If True, create series when they don't exist"
    )
    create_project: bool = Field(
        False, description="If True, create project when it doesn't exist"
    )
    include_stack_trace: bool = Field(
        False, description="If True, include stack trace in the error response"
    )


class ImportRequest(BaseModel):
    data: ImageImportData
    options: ImportOptions


class ImportResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stack_trace: Optional[str] = None


class TaskResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[str] = None
    error: Optional[str] = None


def make_importer(session, options: ImportOptions):
    # Create importer with options
    return Importer(
        session=session,
        create_patients=options.create_patients,
        create_studies=options.create_studies,
        create_series=options.create_series,
        create_projects=options.create_project,
        generate_thumbnails=True,
        run_ai_models=False,  # We handle this separately via background tasks
        config=settings,
    )


@router.post("/import/image", response_model=ImportResponse)
async def import_single_image(
    request: ImportRequest,
    session: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):

    # Create importer with options
    importer = make_importer(session, request.options)

    # Process the date field if it's a string
    image_data = request.data.model_dump()
    image_data["study_date"] = datetime.date.fromisoformat(image_data["study_date"])

    # Execute the import
    try:
        images = importer.import_one(image_data)

    except Exception as e:
        include_stack_trace = request.options.include_stack_trace
        error_message = str(e)
        stack_trace = traceback.format_exc() if include_stack_trace else None

        return ImportResponse(
            success=False,
            message="Import failed",
            error=error_message,
            stack_trace=stack_trace,
        )

    return ImportResponse(
        success=True,
        message="Import completed successfully",
        data={"project_name": image_data["project_name"], "image_count": len(images)},
    )


@router.post("/import/run_inference", response_model=TaskResponse)
async def run_inference(current_user: CurrentUser = Depends(get_current_user)):
    try:
        task = task_run_inference()

        return TaskResponse(
            success=True, message="Inference task queued successfully", task_id=task.id
        )
    except Exception as e:
        return TaskResponse(
            success=False, message="Failed to queue inference task", error=str(e)
        )


@router.post("/import/update_thumbnails", response_model=TaskResponse)
async def update_thumbnails(current_user: CurrentUser = Depends(get_current_user)):
    try:
        task = task_update_thumbnails()

        return TaskResponse(
            success=True,
            message="Thumbnail update task queued successfully",
            task_id=task.id,
        )
    except Exception as e:
        return TaskResponse(
            success=False, message="Failed to queue thumbnail update task", error=str(e)
        )
