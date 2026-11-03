import traceback
from typing import Any, Dict, Literal, Optional

from eyened_orm import ImageInstance
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

from eyened_orm.authz.scope import AccessScope

from ..db import get_db
from ..services.access_scope import get_access_scope
from ..services.acting_user import ActingUser
from ..services.audit_service import AuditService, get_audit_service
from ..services.image_instance_service import (
    ImageInstanceService,
    get_image_instance_service,
)
from eyened_orm.inference.outputs import MODES
from eyened_orm.inference.registry import MODEL_SLUGS, MODELS

from ..utils.tasks import (
    run_model_job,
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


ModelName = Literal[*MODEL_SLUGS]
RunMode = Literal[*MODES]


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


class RunModelRequest(BaseModel):
    """Queue one job per model for the given image instance IDs."""

    image_ids: list[int] = Field(
        ...,
        min_length=1,
        description="ImageInstance IDs; each model only processes images of its modalities.",
    )
    models: Optional[list[ModelName]] = Field(
        None, description="Models to run, or omit to run every registered model."
    )
    mode: RunMode = Field(
        "default",
        description=(
            "default: skip images with output from any version; upgrade: run the current "
            "version where it has no output; failed: retry failed attempts (attribute "
            "models only); overwrite: reprocess everything."
        ),
    )
    upscale: bool = Field(
        False, description="CFI segmentations: store masks in original image space."
    )
    batch_size: Optional[int] = Field(None, description="Default: per model.")
    n_workers: Optional[int] = Field(None, description="Default: per model.")
    commit_interval: Optional[int] = Field(None, description="Default: per output type.")


@router.post("/import/image", response_model=ImportResponse)
def import_single_image(
    request: ImportRequest,
    session: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    audit: AuditService = Depends(get_audit_service),
    scope: AccessScope = Depends(get_access_scope),
):
    # Source data is admin-only (spec 4.4). Outside the try: below, whose
    # except returns a 200 with success=False -- a denial swallowed into that
    # would read as a failed import rather than a refusal.
    scope.require_admin(entity="ImageInstance")
    try:
        # Run the new importer on a single row
        import_run = plan_image_import(session=session, rows=[request.data])
        import_run.apply()
        # Count created image instances for logging/response
        image_creates = [
            change
            for change in import_run.changes
            if isinstance(change, ImportCreate)
            and isinstance(change.entity, ImageInstance)
        ]
        image_count = len(image_creates)

        audit.record(
            action="INSERT",
            entity="Import",
            actor=ActingUser(id=current_user.id, username=current_user.username),
            changes={
                "project_name": request.data.project_name,
                "images_created": image_count,
            },
        )

    except Exception as e:
        # A caught exception here means the request still returns normally (200,
        # success=False below), so get_db would otherwise commit whatever
        # import_run.apply() staged before failing. Roll back first so a failed
        # import leaves nothing.
        session.rollback()
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


@router.post("/import/run_model", response_model=TaskResponse)
def enqueue_run_model(
    body: RunModelRequest,
    current_user: CurrentUser = Depends(get_current_user),
    images: ImageInstanceService = Depends(get_image_instance_service),
):
    """Queue one RQ job per model; each model's queue is named after its slug."""
    # Before the try:, never inside it -- the except below turns any raise into
    # a 200 with success=False, so a gate moved in there would report a denial
    # as a queue failure and the status assertions would pass for the wrong
    # reason.
    images.require_grader_on_images(body.image_ids)

    from ..main import get_rq_queue

    try:
        task_ids: list[str] = []
        for slug in body.models or MODEL_SLUGS:
            task_id = str(uuid.uuid4())
            get_rq_queue(slug).enqueue(
                run_model_job,
                body.image_ids,
                slug,
                body.mode,
                body.upscale,
                body.batch_size,
                body.n_workers,
                body.commit_interval,
                job_id=task_id,
                job_timeout=MODELS[slug].job_timeout(len(body.image_ids)),
            )
            task_ids.append(task_id)
        return TaskResponse(
            success=True,
            message=f"{len(task_ids)} model task(s) queued successfully",
            task_id=task_ids[0],
            task_ids=task_ids,
        )
    except Exception as e:
        return TaskResponse(
            success=False, message="Failed to queue model task(s)", error=str(e)
        )


@router.post("/import/update_thumbnails", response_model=TaskResponse)
def post_import_update_thumbnails(
    failed: bool = Query(
        False,
        description="Include images with empty ThumbnailPath (failed previous run), like ``eorm update-thumbnails --failed``.",
    ),
    print_errors: bool = Query(
        False,
        description="Print per-image errors on the worker, like ``eorm update-thumbnails --print-errors``.",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    scope: AccessScope = Depends(get_access_scope),
):
    """Queue a job that scans the DB for missing thumbnails (CLI-equivalent)."""
    # A whole-database sweep is a maintenance operation over every project's
    # images, so it sits at admin rather than at a per-project floor. Outside
    # the try: for the same reason as every other gate in this module.
    scope.require_admin(entity="ImageInstance")

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
def post_import_update_thumbnails_for_image_ids(
    body: UpdateThumbnailsForImageIdsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    images: ImageInstanceService = Depends(get_image_instance_service),
):
    """Queue thumbnail generation for the given ``image_ids`` only."""
    images.require_grader_on_images(body.image_ids)

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
def get_status(
    task_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return a queued job's status and result.

    Authenticated, but not scope-aware, and that is not an oversight: every RQ
    entrypoint returns a bare bool (pinned by
    test_every_rq_entrypoint_returns_a_bare_bool), so there is no project data
    in the response to filter. Job ids are uuid4 and not enumerable here, so
    this is a capability control -- but a capability that leaks through a log
    line or a screenshot would otherwise need no credential at all.
    """
    from ..main import redis_conn

    try:
        job = Job.fetch(task_id, connection=redis_conn)
        return {"task_id": task_id, "status": job.get_status(), "result": job.result}
    except NoSuchJobError:
        return {"error": "job not found"}
