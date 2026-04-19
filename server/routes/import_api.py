import traceback
from typing import Any, Dict, Optional

from eyened_orm import ImageInstance
from eyened_orm.importer import ImportRow, run_import
from eyened_orm.importer.import_run import ImportCreate
from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasic
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.routes.auth import CurrentUser, get_current_user
import uuid
from rq.job import Job
from rq.exceptions import NoSuchJobError

from ..db import get_db
from ..utils.db_logging import get_db_logger
from ..utils.tasks import update_thumbnails

router = APIRouter()
security = HTTPBasic()


# Pydantic models for request and response schemas
# ImportRow (alias InstancePOSTFlat) is the flat per-image import payload


class ImportOptions(BaseModel):
    """
    Options for the import process
    """

    include_stack_trace: bool = Field(
        False, description="If True, include stack trace in the error response"
    )


class ImportRequest(BaseModel):
    data: ImportRow
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


@router.post("/import/image", response_model=ImportResponse)
async def import_single_image(
    request: ImportRequest,
    session: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        # Run the new importer on a single row
        import_run = run_import(session=session, rows=[request.data])

        # Count created image instances for logging/response
        image_creates = [
            change
            for change in import_run.changes
            if isinstance(change, ImportCreate)
            and isinstance(change.entity, ImageInstance)
        ]
        image_count = len(image_creates)

        logger = get_db_logger()
        if logger:
            logger.log_insert(
                user=current_user.username,
                user_id=current_user.id,
                endpoint="POST /api/import/image",
                entity="Import",
                summary={
                    "project_name": request.data.project_name,
                    "images_created": image_count,
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
        data={
            "project_name": request.data.project_name,
            "image_count": image_count,
            "import_run_id": import_run.import_run_id,
        },
    )


# @router.post("/import/run_inference", response_model=TaskResponse)
# async def run_inference(current_user: CurrentUser = Depends(get_current_user)):
#     try:
#         task = task_run_inference()

#         return TaskResponse(
#             success=True, message="Inference task queued successfully", task_id=task.id
#         )
#     except Exception as e:
#         return TaskResponse(
#             success=False, message="Failed to queue inference task", error=str(e)
#         )


@router.post("/import/update_thumbnails", response_model=TaskResponse)
async def update_thumbnails(current_user: CurrentUser = Depends(get_current_user)):
    from ..main import queue
 
    try:
        task_id = str(uuid.uuid4())

        job = queue.enqueue(
                update_thumbnails,
                task_id,
                job_id=task_id
            )


        return TaskResponse(
            success=True,
            message="Thumbnail update task queued successfully",
            task_id=task_id,
        )
    except Exception as e:
        return TaskResponse(
            success=False, message="Failed to queue thumbnail update task", error=str(e)
        )

@router.get("/import/status/{task_id}")
def get_status(task_id: str):
    from ..main import redis_conn
    try:
        job = Job.fetch(task_id, connection=redis_conn)
        return {
            "task_id": task_id,
            "status": job.get_status(),
            "result": job.result
        }
    except NoSuchJobError:
        return {"error": "job not found"}