from typing import List, Optional, Union

from fastapi import APIRouter, Depends, Response

from eyened_orm import SubTaskState

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_tasks import (
    SubTaskGET,
    SubTasksResponse,
    SubTasksWithImagesResponse,
    SubTaskWithImagesGET,
    TaskGET,
    TaskPATCH,
    TaskPUT,
)
from ..services.task_service import TaskService, get_task_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.post("/task", response_model=TaskGET)
def create_task(
    dto: TaskPUT,
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a task owned by the current user."""
    task = service.create_task(
        dto.name,
        dto.description,
        dto.contact_id,
        dto.task_definition_id,
    )
    # A task is created with no subtasks, so it spans nothing yet.
    return DTOConverter.task_to_get(task, num_tasks=0, num_tasks_ready=0, projects=[])


@router.get("/task", response_model=List[TaskGET])
def list_tasks(
    include_projects: bool = False,
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all tasks (no pagination).

    ``include_projects`` is off by default: resolving the projects each task
    spans walks every image link of every task, and no client renders the
    field today. Omitted, ``projects`` is ``null`` rather than ``[]`` --
    "not requested", not "spans nothing".
    """
    tasks, counts, projects = service.list_tasks(include_projects=include_projects)
    return [
        DTOConverter.task_to_get(
            t,
            num_tasks=counts[t.TaskID][0],
            num_tasks_ready=counts[t.TaskID][1],
            projects=None if projects is None else projects[t.TaskID],
        )
        for t in tasks
    ]


@router.get("/task/{task_id}", response_model=TaskGET)
def get_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single task with its subtask counts."""
    task, (num_tasks, num_tasks_ready), projects = service.get_task(task_id)
    return DTOConverter.task_to_get(
        task, num_tasks=num_tasks, num_tasks_ready=num_tasks_ready, projects=projects
    )


@router.patch("/task/{task_id}", response_model=TaskGET)
def patch_task(
    task_id: int,
    dto: TaskPATCH,
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a task's name/description/contact/definition/state."""
    task, (num_tasks, num_tasks_ready), projects = service.update_task(
        task_id,
        dto.name,
        dto.description,
        dto.contact_id,
        dto.task_definition_id,
        dto.task_state,
    )
    return DTOConverter.task_to_get(
        task, num_tasks=num_tasks, num_tasks_ready=num_tasks_ready, projects=projects
    )


@router.delete("/task/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a task."""
    service.delete_task(
        task_id,
    )
    return Response(status_code=204)


@router.get(
    "/task/{task_id}/subtasks",
    response_model=Union[SubTasksWithImagesResponse, SubTasksResponse],
)
def list_subtasks(
    task_id: int,
    with_images: bool = False,
    limit: int = 200,
    page: int = 0,
    subtask_status: Optional[SubTaskState] = None,
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List subtasks of a task (pagination, optional images, optional status filter).

    ``index`` is the 0-based position within all subtasks of the task ordered by
    SubTaskID (computed before any subtask_status filtering).
    """
    rows_with_index, count = service.list_task_subtasks(
        task_id,
        with_images=with_images,
        limit=limit,
        page=page,
        status=subtask_status,
    )
    convert = (
        DTOConverter.subtask_with_images_to_get
        if with_images
        else DTOConverter.subtask_to_get
    )
    subtasks = [
        convert(st).copy(update={"index": index}) for st, index in rows_with_index
    ]
    return {"subtasks": subtasks, "limit": limit, "page": page, "count": count}


@router.get(
    "/task/{task_id}/subtask/{subtask_index}",
    response_model=Union[SubTaskWithImagesGET, SubTaskGET],
)
def get_subtask(
    task_id: int,
    subtask_index: int,
    with_images: bool = False,
    with_next: bool = False,
    service: TaskService = Depends(get_task_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single subtask by index, optionally with images and the next subtask."""
    main, nxt = service.get_task_subtask(
        task_id,
        subtask_index,
        with_images=with_images,
        with_next=with_next,
    )
    convert = (
        DTOConverter.subtask_with_images_to_get
        if with_images
        else DTOConverter.subtask_to_get
    )
    main_dto = convert(main).copy(update={"index": subtask_index})
    if nxt is not None:
        next_dto = convert(nxt).copy(update={"index": subtask_index + 1})
        main_dto = main_dto.copy(update={"next_task": next_dto})
    return main_dto
