import traceback
from typing import Any, Dict, Optional

from eyened_orm.importer.importer import Importer
from eyened_orm.importer.importer_dtos import InstancePOSTFlat
from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasic
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.routes.auth import CurrentUser, get_current_user

from ..config import settings
from ..db import get_db
from ..utils.db_logging import get_db_logger
from ..utils.huey import task_run_inference, task_update_thumbnails

router = APIRouter()
security = HTTPBasic()


# Pydantic models for request and response schemas
# InstancePOSTFlat is used as ImageImportData replacement


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
    data: InstancePOSTFlat
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

    # Execute the import
    try:
        images = importer.import_one(request.data)
        
        # Log import summary (not individual images)
        logger = get_db_logger()
        if logger:
            logger.log_insert(
                user=current_user.username,
                user_id=current_user.id,
                endpoint="POST /api/import/image",
                entity="Import",
                summary={
                    "project_name": request.data.project_name,
                    "images_created": len(images),
                    "create_patients": request.options.create_patients,
                    "create_studies": request.options.create_studies,
                    "create_series": request.options.create_series,
                    "create_project": request.options.create_project,
                },
            )

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
        data={"project_name": request.data.project_name, "image_count": len(images)},
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
