from eyened_orm import (
    AnnotationType,
    AnnotationTypeBase,
    CompositeFeature,
    CompositeFeatureBase,
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
    SubTaskImageLink,
    Tag,
    TagBase,
    Task,
    TaskBase,
    TaskDefinition,
    TaskDefinitionBase,
    TaskState,
    TaskStateBase,
)
from eyened_orm.base import create_patch_model
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session
import inspect

from server.routes.utils import collect_rows

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


def get_pk_columns(model_class):
    return [col.name for col in model_class.__table__.primary_key.columns]

def get_item_by_pk(db, model_class, pk_values: dict, soft_delete_field: str | None):
    query = db.query(model_class)
    for col, val in pk_values.items():
        query = query.filter(getattr(model_class, col) == val)
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
    pk_columns = get_pk_columns(model_class)

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

    # --- PK-based routes (merged for single and composite PKs) ---
    pk_path = "/".join([f"{{{col}}}" for col in pk_columns])

    def make_handler(
        pk_columns, method, PatchModel, model_class, soft_delete_field,
        get_item_by_pk, get_db, get_current_user, CurrentUser
    ):
        from fastapi import Depends, Path, HTTPException
        from sqlalchemy.orm import Session

        # Build the argument string for the function definition
        arg_str = ", ".join([f"{col}: int = Path(...)" for col in pk_columns])
        # Add dependencies
        if method == "patch":
            arg_str += ", params: PatchModel = None"
        arg_str += ", db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)"

        # Build the pk_values dict
        pk_dict_str = "{" + ", ".join([f"'{col}': {col}" for col in pk_columns]) + "}"

        # Handler logic as a string
        if method == "get":
            body = f"""
def handler({arg_str}):
    pk_values = {pk_dict_str}
    return get_item_by_pk(db, model_class, pk_values, soft_delete_field)
"""
        elif method == "patch":
            body = f"""
def handler({arg_str}):
    pk_values = {pk_dict_str}
    item = get_item_by_pk(db, model_class, pk_values, soft_delete_field)
    for key, value in params.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item
"""
        elif method == "delete":
            body = f"""
def handler({arg_str}):
    pk_values = {pk_dict_str}
    query = db.query(model_class)
    for col, val in pk_values.items():
        query = query.filter(getattr(model_class, col) == val)
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{{model_class.__name__}} not found")
    if soft_delete_field:
        setattr(item, soft_delete_field, True)
        db.commit()
    else:
        db.delete(item)
        db.commit()
    return None
"""
        # Define the function in a local namespace, passing all required objects
        local_vars = {}
        exec(
            body,
            {
                "PatchModel": PatchModel,
                "model_class": model_class,
                "soft_delete_field": soft_delete_field,
                "get_item_by_pk": get_item_by_pk,
                "Depends": Depends,
                "Path": Path,
                "Session": Session,
                "CurrentUser": CurrentUser,
                "HTTPException": HTTPException,
                "get_db": get_db,
                "get_current_user": get_current_user,
            },
            local_vars,
        )
        return local_vars["handler"]

    # Register the routes
    router.add_api_route(
        f"/{route_prefix}/" + pk_path,
        make_handler(pk_columns, "get", PatchModel, model_class, soft_delete_field, get_item_by_pk, get_db, get_current_user, CurrentUser),
        response_model=model_class,
        methods=["GET"],
    )
    router.add_api_route(
        f"/{route_prefix}/" + pk_path,
        make_handler(pk_columns, "patch", PatchModel, model_class, soft_delete_field, get_item_by_pk, get_db, get_current_user, CurrentUser),
        response_model=model_class,
        methods=["PATCH"],
    )
    router.add_api_route(
        f"/{route_prefix}/" + pk_path,
        make_handler(pk_columns, "delete", PatchModel, model_class, soft_delete_field, get_item_by_pk, get_db, get_current_user, CurrentUser),
        status_code=204,
        methods=["DELETE"],
    )

    return router


def create_linking_routes(model_resource, model_class, parent, child_route, child):

    parent_resource, parent_class = parent
    child_resource, child_class = child
    parent_id_field = parent_class.__table__.primary_key.columns[0].name
    child_id_field = child_class.__table__.primary_key.columns[0].name

    @router.get(
        f"/{parent_resource}/{{parent_id}}/{child_route}",
        response_model=list[model_class],
    )
    async def list_items(
        parent_id: int,
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ):
        query = db.query(model_class).filter(
            getattr(model_class, parent_id_field) == parent_id
        )
        return query.all()

    @router.post(
        f"/{parent_resource}/{{parent_id}}/{child_route}/{{child_id}}",
        response_model=dict,
        status_code=201,
    )
    async def create_item(
        parent_id: int,
        child_id: int,
        item: model_class,
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ):
        """Create a new linking item."""
        db_item = model_class(
            **{
                parent_id_field: parent_id,
                child_id_field: child_id,
                **item.model_dump(),
            }
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)

        # Get the actual related objects
        parent_item = db.get(parent_class, parent_id)
        child_item = db.get(child_class, child_id)

        return {
            parent_resource: [parent_item],
            child_resource: [child_item],
            model_resource: [db_item],
        }


    @router.delete(
        f"/{parent_resource}/{{parent_id}}/{child_route}/{{child_id}}",
        status_code=204,
    )
    async def delete_item(
        parent_id: int,
        child_id: int,
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user),
    ):
        """Delete a linking item by parent and child IDs."""
        query = db.query(model_class).filter(
            getattr(model_class, parent_id_field) == parent_id,
            getattr(model_class, child_id_field) == child_id,
        )
        try:
            item = query.one()
        except NoResultFound:
            raise HTTPException(
                status_code=404, detail=f"{model_class.__name__} not found"
            )
        except MultipleResultsFound:
            raise HTTPException(
                status_code=400, detail=f"{model_class.__name__} multiple results found"
            )

        db.delete(item)
        db.commit()
        return None

    return router


create_crud_routes(
    ImageInstance, ImageInstanceBase, "instances", soft_delete_field="Inactive"
)
create_crud_routes(Study, StudyBase, "studies")
create_crud_routes(Series, SeriesBase, "series")
create_crud_routes(Patient, PatientBase, "patients")
create_crud_routes(Project, ProjectBase, "projects")
create_crud_routes(Contact, ContactBase, "contacts")

create_crud_routes(Feature, FeatureBase, "features")
create_crud_routes(CompositeFeature, CompositeFeatureBase, "composite-features")

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


create_linking_routes(
    "sub-task-image-links",
    SubTaskImageLink,
    ("sub-tasks", SubTask),
    "image-links",
    ("instances", ImageInstance),
)


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


@router.get("/tasks/{task_id}/sub-tasks-with-images")
async def get_task_subtasks_with_images(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get all subtasks for a task along with their associated image links and image instances."""
    # Get all subtasks for this task
    subtasks = db.query(SubTask).filter(SubTask.TaskID == task_id).all()

    # Get all image links for these subtasks
    links = (
        db.query(SubTaskImageLink)
        .filter(SubTaskImageLink.SubTaskID.in_({st.SubTaskID for st in subtasks}))
        .all()
    )

    # Get all related image instances
    image_ids = {link.ImageInstanceID for link in links}

    instances = ImageInstance.by_ids(db, image_ids)
    series_ids = {instance.SeriesID for instance in instances}
    series = Series.by_ids(db, series_ids)
    study_ids = {series.StudyID for series in series}
    studies = Study.by_ids(db, study_ids)
    patient_ids = {study.PatientID for study in studies}
    patients = Patient.by_ids(db, patient_ids)

    return {
        "sub-tasks": subtasks,
        "sub-task-image-links": links,
        **{
            k: collect_rows(v)
            for k, v in {
                "instances": instances,
                "series": series,
                "studies": studies,
                "patients": patients,
            }.items()
        },
    }


@router.get("/form-annotations/{form_annotation_id}/form-data")
async def get_form_annotation_form_data(
    form_annotation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation = FormAnnotation.by_id(db, form_annotation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="FormAnnotation not found")

    return annotation.FormData
