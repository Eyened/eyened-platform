import traceback
from typing import Any, Dict, Literal, Optional

from eyened_orm import ImageInstance
from eyened_orm.commands.model_processing import CFI_ATTRIBUTE_MODEL_SLUGS
from eyened_orm.importer import ImportRow, plan_image_import
from eyened_orm.importer.import_run import ImportCreate
from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPBasic
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.routes.auth import CurrentUser, get_current_user
import uuid
from rq.job import Job
from rq.exceptions import NoSuchJobError

from ..db import get_db
from ..utils.db_logging import get_db_logger
from ..utils.tasks import (
    run_cfi_model_for_image_ids,
    run_thumbnail_update_for_image_ids_job,
    run_thumbnail_update_job,
)

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
    task_ids: Optional[list[str]] = None
    error: Optional[str] = None


CfiModelName = Literal[
    "cfi-roi",
    "cfi-keypoints",
    "cfi-odfd",
    "cfi-quality",
    "cfi-amd",
]


class UpdateThumbnailsForImageIdsRequest(BaseModel):
    """Queue thumbnail generation for specific instances (same processing as bulk update)."""

    image_ids: list[int] = Field(
        ...,
        min_length=1,
        description="ImageInstance IDs to generate thumbnails for.",
    )
    print_errors: bool = Field(
        False, description="Log per-image errors to worker stdout."
    )


class RunCfiModelsRequest(BaseModel):
    """Queue a CFI model job for the given image instance IDs."""

    image_ids: list[int] = Field(
        ...,
        min_length=1,
        description="ImageInstance IDs to process (e.g. ColorFundus IDs from a completed import).",
    )
    model: Optional[CfiModelName] = Field(
        None,
        description="Single pipeline to run, or omit to run all in default order.",
    )
    overwrite: bool = Field(
        False, description="If true, re-run even when results already exist."
    )
    commit_interval: int = 100
    batch_size: int = 8
    n_workers: int = 16


@router.post("/import/image", response_model=ImportResponse)
async def import_single_image(
    request: ImportRequest,
    session: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        # Run the new importer on a single row
        import_run = plan_image_import(session=session, rows=[request.data])
        import_run.apply()
        session.commit()
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


@router.post("/import/run_cfi_models", response_model=TaskResponse)
async def enqueue_run_cfi_models(
    body: RunCfiModelsRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Queue one RQ job per model, each on its own queue (``cfi-roi``, ...)."""
    from rq import Queue

    from ..main import get_rq_queue

    try:
        models = (
            [body.model] if body.model is not None else list(CFI_ATTRIBUTE_MODEL_SLUGS)
        )
        task_ids: list[str] = []
        for m in models:
            q: Queue = get_rq_queue(m)
            task_id = str(uuid.uuid4())
            q.enqueue(
                run_cfi_model_for_image_ids,
                body.image_ids,
                m,
                body.overwrite,
                body.commit_interval,
                body.batch_size,
                body.n_workers,
                job_id=task_id,
            )
            task_ids.append(task_id)
        return TaskResponse(
            success=True,
            message="CFI models task(s) queued successfully",
            task_id=task_ids[0],
            task_ids=task_ids,
        )
    except Exception as e:
        return TaskResponse(
            success=False,
            message="Failed to queue CFI models task",
            error=str(e),
        )


@router.post("/import/update_thumbnails", response_model=TaskResponse)
async def post_import_update_thumbnails(
    failed: bool = Query(
        False,
        description="Include images with empty ThumbnailPath (failed previous run), like ``eorm update-thumbnails --failed``.",
    ),
    print_errors: bool = Query(
        False,
        description="Print per-image errors on the worker, like ``eorm update-thumbnails --print-errors``.",
    ),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Queue a job that scans the DB for missing thumbnails (CLI-equivalent)."""
    from ..main import queue

    try:
        task_id = str(uuid.uuid4())
        queue.enqueue(
            run_thumbnail_update_job,
            failed,
            print_errors,
            job_id=task_id,
        )
        return TaskResponse(
            success=True,
            message="Thumbnail update task queued successfully",
            task_id=task_id,
        )
    except Exception as e:
        return TaskResponse(
            success=False,
            message="Failed to queue thumbnail update task",
            error=str(e),
        )


@router.post("/import/update_thumbnails_for_image_ids", response_model=TaskResponse)
async def post_import_update_thumbnails_for_image_ids(
    body: UpdateThumbnailsForImageIdsRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Queue thumbnail generation for the given ``image_ids`` only."""
    from ..main import queue

    try:
        task_id = str(uuid.uuid4())
        queue.enqueue(
            run_thumbnail_update_for_image_ids_job,
            body.image_ids,
            body.print_errors,
            job_id=task_id,
        )
        return TaskResponse(
            success=True,
            message="Thumbnail update (by image IDs) queued successfully",
            task_id=task_id,
        )
    except Exception as e:
        return TaskResponse(
            success=False,
            message="Failed to queue thumbnail-by-id task",
            error=str(e),
        )


@router.get("/import/status/{task_id}")
def get_status(task_id: str):
    from ..main import redis_conn

    try:
        job = Job.fetch(task_id, connection=redis_conn)
        return {"task_id": task_id, "status": job.get_status(), "result": job.result}
    except NoSuchJobError:
        return {"error": "job not found"}
