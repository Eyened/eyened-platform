from eyened_orm import (
    Annotation,
    AnnotationBase,
    AnnotationType,
    AnnotationTypeBase,
    Contact,
    ContactBase,
    Creator,
    CreatorBase,
    DeviceInstance,
    DeviceInstanceBase,
    DeviceModel,
    DeviceModelBase,
    Feature,
    FeatureBase,
    FormAnnotation,
    FormAnnotationBase,
    FormSchema,
    FormSchemaBase,
    ImageInstance,
    ImageInstanceBase,
    Patient,
    PatientBase,
    Project,
    ProjectBase,
    Scan,
    ScanBase,
    Series,
    SeriesBase,
    Study,
    StudyBase,
    SubTask,
    SubTaskBase,
    Tag,
    TagBase,
    Task,
    TaskBase,
    TaskDefinition,
    TaskDefinitionBase,
    TaskState,
    TaskStateBase,
    SubTaskImageLink,
    SubTaskImageLinkBase,
)
from eyened_orm.base import create_patch_model
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .auth import CurrentUser, get_current_user

router = APIRouter()


def get_item_or_404(
    db: Session, model_class, item_id: int, soft_delete_field: str | None
):
    pk = model_class.__table__.primary_key.columns[0]
    print("pk", pk, "item_id", item_id)
    query = db.query(model_class).filter(pk == item_id)
    if soft_delete_field:
        query = query.filter(getattr(model_class, soft_delete_field) == False)
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{model_class.__name__} not found")
    return item


def create_crud_routes(
    model_class,
    base_model,
    route_prefix: str,
    soft_delete_field: str | None = None,
):
    """
    Creates a set of CRUD routes for a given model.

    Args:
        model_class: SQLModel model class
        base_model: Pydantic base model for the entity
        route_prefix: URL prefix for the routes (e.g. "images" for /images/...)
        soft_delete_field: Optional field name to use for soft delete (e.g. "Inactive")
    """

    # PatchModel is a Pydantic model with all fields optional
    # useful for filtering on columns and for patching (partial updates)
    PatchModel = create_patch_model(f"{model_class.__name__}Patch", base_model)

    # assuming single column primary key
    pk = model_class.__table__.primary_key.columns[0]

    @router.get(f"/{route_prefix}", response_model=list[model_class])
    async def list_items(
        filter: PatchModel = Depends(),  # FastAPI will parse all query params into this model
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ):
        query = db.query(model_class)

        # Add soft delete filter if specified
        if soft_delete_field:
            query = query.filter(getattr(model_class, soft_delete_field) == False)

        conditions = [
            getattr(model_class, key) == value
            for key, value in filter.model_dump().items()
            if value is not None
        ]

        if conditions:
            query = query.filter(*conditions)

        return query.all()

    @router.get(f"/{route_prefix}/{{item_id}}", response_model=model_class)
    async def get_item(
        item_id: int,
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ):
        """Get a specific item by ID."""
        return get_item_or_404(db, model_class, item_id, soft_delete_field)

    @router.post(f"/{route_prefix}", response_model=model_class, status_code=201)
    async def create_item(
        item: base_model,
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ):
        """Create a new item."""
        db_item = model_class(**item.model_dump())
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item

    @router.patch(f"/{route_prefix}/{{item_id}}", response_model=model_class)
    async def patch_item(
        item_id: int,
        params: PatchModel,
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ):
        print("patching item", item_id)
        item = get_item_or_404(db, model_class, item_id, soft_delete_field)
        for key, value in params.model_dump().items():
            if value is not None:
                setattr(item, key, value)
        db.commit()
        db.refresh(item)
        return item

    @router.delete(f"/{route_prefix}/{{item_id}}", status_code=204)
    async def delete_item(
        item_id: int,
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ):
        """Delete an item by ID."""
        item = db.get(model_class, item_id)
        if not item:
            raise HTTPException(
                status_code=404, detail=f"{model_class.__name__} not found"
            )

        if soft_delete_field:
            setattr(item, soft_delete_field, True)
            db.commit()
        else:
            db.delete(item)
            db.commit()
        return None

    return router


def create_linking_routes(
    model_class,
    base_model,
    route_prefix: str,
):
    """
    Creates a set of CRUD routes for a linking table with composite primary key.

    Args:
        model_class: SQLModel model class
        base_model: Pydantic base model for the entity
        route_prefix: URL prefix for the routes (e.g. "subtask-images" for /subtask-images/...)
    """
    # PatchModel is a Pydantic model with all fields optional
    # useful for filtering on columns
    PatchModel = create_patch_model(f"{model_class.__name__}Patch", base_model)

    # Get all primary key columns
    pk_columns = model_class.__table__.primary_key.columns

    @router.get(f"/{route_prefix}", response_model=list[model_class])
    async def list_items(
        filter: PatchModel = Depends(),  # FastAPI will parse all query params into this model
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ):
        query = db.query(model_class)

        conditions = [
            getattr(model_class, key) == value
            for key, value in filter.model_dump().items()
            if value is not None
        ]

        if conditions:
            query = query.filter(*conditions)

        return query.all()

    # Create the route path with named parameters for each primary key
    pk_path_params = "/".join(f"{{{col.name}}}" for col in pk_columns)
    route_path = f"/{route_prefix}/{pk_path_params}"

    @router.post(f"/{route_prefix}", response_model=model_class, status_code=201)
    async def create_item(
        item: base_model,
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ):
        """Create a new linking item."""
        db_item = model_class(**item.model_dump())
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item

    @router.delete(route_path, status_code=204)
    async def delete_item(
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
        **pk_values: int,  # This will capture all the named parameters
    ):
        """Delete a linking item by composite ID."""
        # Build the filter conditions for each primary key column
        conditions = [col == pk_values[col.name] for col in pk_columns]

        query = db.query(model_class).filter(*conditions)
        item = query.first()
        if not item:
            raise HTTPException(
                status_code=404, detail=f"{model_class.__name__} not found"
            )

        db.delete(item)
        db.commit()
        return None

    return router


create_crud_routes(
    ImageInstance, ImageInstanceBase, "images", soft_delete_field="Inactive"
)
create_crud_routes(Study, StudyBase, "studies")
create_crud_routes(Series, SeriesBase, "series")
create_crud_routes(Patient, PatientBase, "patients")
create_crud_routes(Project, ProjectBase, "projects")
create_crud_routes(Contact, ContactBase, "contacts")

create_crud_routes(Feature, FeatureBase, "features")
create_crud_routes(Creator, CreatorBase, "creators")
create_crud_routes(Tag, TagBase, "tags")
create_crud_routes(Scan, ScanBase, "scans")
create_crud_routes(AnnotationType, AnnotationTypeBase, "annotation-types")
create_crud_routes(Task, TaskBase, "tasks")
create_crud_routes(TaskDefinition, TaskDefinitionBase, "task-definitions")
create_crud_routes(TaskState, TaskStateBase, "task-states")
create_crud_routes(SubTask, SubTaskBase, "sub-tasks")

create_crud_routes(FormSchema, FormSchemaBase, "form-schemas")
create_crud_routes(DeviceModel, DeviceModelBase, "device-models")
create_crud_routes(DeviceInstance, DeviceInstanceBase, "device-instances")
create_crud_routes(
    FormAnnotation, FormAnnotationBase, "form-annotations", soft_delete_field="Inactive"
)
create_crud_routes(
    Annotation, AnnotationBase, "annotations", soft_delete_field="Inactive"
)

create_linking_routes(SubTaskImageLink, SubTaskImageLinkBase, "sub-task-image-links")


@router.get(
    "/tasks/{task_id}/sub-task-image-links", response_model=list[SubTaskImageLink]
)
async def get_task_subtask_image_links(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get all SubTaskImageLinks for subtasks belonging to a specific task."""
    return (
        db.query(SubTaskImageLink).join(SubTask).filter(SubTask.TaskID == task_id).all()
    )


@router.get("/tasks/{task_id}/subtasks-with-images")
async def get_task_subtasks_with_images(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get all subtasks for a task along with their associated image links and image instances."""
    # Get all subtasks for this task
    subtasks = db.query(SubTask).filter(SubTask.TaskID == task_id).all()
    subtask_ids = {st.SubTaskID for st in subtasks}

    # Get all image links for these subtasks
    image_links = (
        db.query(SubTaskImageLink)
        .filter(SubTaskImageLink.SubTaskID.in_(subtask_ids))
        .all()
    )
    image_ids = {link.ImageInstanceID for link in image_links   }

    # Get all related image instances
    image_instances = (
        db.query(ImageInstance)
        .filter(ImageInstance.ImageInstanceID.in_(image_ids))
        .all()
    )

    return {
        "sub-tasks": subtasks,
        "sub-task-image-links": image_links,
        "instances": image_instances,
    }
