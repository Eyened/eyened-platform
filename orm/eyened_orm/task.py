from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, List, Optional, Iterable

from sqlalchemy import (
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    String,
    UniqueConstraint,
    select,
    func,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import (
        Contact,
        Creator,
        FormAnnotation,
        ImageInstance,
        SubTask,
        TaskDefinition,
        SubTaskState,
        Segmentation,
    )


class TaskDefinition(Base):
    __tablename__ = "TaskDefinition"
    _name_column: ClassVar[str | None] = "TaskDefinitionName"

    TaskDefinitionID: Mapped[int] = mapped_column(primary_key=True)
    TaskDefinitionName: Mapped[str] = mapped_column(String(256))
    TaskConfig: Mapped[dict | None] = mapped_column(JSON)

    Tasks: Mapped[List["Task"]] = relationship(
        "eyened_orm.task.Task", back_populates="TaskDefinition"
    )
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())


class SubTaskState(Enum):
    NotStarted = "NotStarted"
    Busy = "Busy"
    Ready = "Ready"


class TaskState(Enum):
    NotStarted = "NotStarted"
    Busy = "Busy"
    Finished = "Finished"
    Aborted = "Aborted"
    Archived = "Archived"


class TaskProject(Base):
    """The projects a task declares. Authoritative, not derived.

    A task's images must lie within this set -- enforced by
    ``SubTaskImageLink (TaskID, ProjectID) -> TaskProject``, not by
    application code. Adding an image from an undeclared project is refused by
    the database; removing an image never changes the declaration.

    ``ondelete="RESTRICT"`` on ProjectID because deleting a project out from
    under a task's declaration would silently widen who can see that task.
    """

    __tablename__ = "TaskProject"
    __table_args__ = (
        # Named because InnoDB requires an index on the referencing side of the
        # ProjectID foreign key and creates one itself, called `ProjectID`, if
        # we do not. That index is undeclarable in the model and undroppable in
        # the database (ERROR 1553: "needed in a foreign key constraint"), so
        # every later `alembic revision --autogenerate` emits a remove_index for
        # it, forever.
        Index("ix_TaskProject_Project", "ProjectID"),
    )

    # `fk_TaskProject_Task` is named, and the name is load-bearing: InnoDB walks
    # a parent's referencing constraints in constraint-id order, and this name
    # is chosen to lose that race against SubTask's key to `Task`. A guard in
    # the containment migration refuses to run if that ordering stops holding.
    TaskID: Mapped[int] = mapped_column(
        ForeignKey("Task.TaskID", ondelete="CASCADE", name="fk_TaskProject_Task"),
        primary_key=True,
    )
    ProjectID: Mapped[int] = mapped_column(
        ForeignKey(
            "Project.ProjectID", ondelete="RESTRICT", name="fk_TaskProject_Project"
        ),
        primary_key=True,
    )
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())

    # Needed to attach a declaration to a Task that is still pending: only the
    # relationship can carry TaskID across an INSERT that has not happened yet,
    # and the importer and create_from_imagesets both build the Task and its
    # declaration in one flush.
    Task: Mapped["Task"] = relationship(
        "eyened_orm.task.Task", back_populates="TaskProjects"
    )


class Task(Base):
    __tablename__ = "Task"
    __table_args__ = (
        Index("fk_Task_TaskDefinition1_idx", "TaskDefinitionID"),
        Index("ix_Task_Creator_TaskDefinition", "CreatorID", "TaskDefinitionID"),
    )
    _name_column: ClassVar[str | None] = "TaskName"

    TaskID: Mapped[int] = mapped_column(primary_key=True)
    TaskName: Mapped[str] = mapped_column(String(256))
    Description: Mapped[Optional[str]] = mapped_column(Text)
    CreatorID: Mapped[Optional[int]] = mapped_column(ForeignKey("Creator.CreatorID"))
    ContactID: Mapped[Optional[int]] = mapped_column(ForeignKey("Contact.ContactID"))
    TaskDefinitionID: Mapped[int] = mapped_column(
        ForeignKey("TaskDefinition.TaskDefinitionID")
    )
    # TaskStateID: Mapped[Optional[int]] = mapped_column(ForeignKey("TaskState.TaskStateID"))

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())

    Contact: Mapped[Optional["Contact"]] = relationship(
        "eyened_orm.project.Contact", back_populates="Tasks"
    )

    Creator: Mapped["Creator"] = relationship(
        "eyened_orm.creator.Creator", back_populates="Tasks"
    )
    TaskDefinition: Mapped["TaskDefinition"] = relationship(
        "eyened_orm.task.TaskDefinition", back_populates="Tasks"
    )
    TaskState: Mapped["TaskState"]

    SubTasks: Mapped[List["SubTask"]] = relationship(
        "eyened_orm.task.SubTask",
        back_populates="Task",
        passive_deletes=True,
    )

    TaskProjects: Mapped[List["TaskProject"]] = relationship(
        "eyened_orm.task.TaskProject",
        back_populates="Task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @classmethod
    def create_from_imagesets(
        cls: type["Task"],
        session: Session,
        taskdef_name: str,
        task_name: str,
        imagesets: Iterable[Iterable[int | ImageInstance]],
        creator_name: str | None = None,
        *,
        projects: Iterable[int] | None = None,
    ) -> "Task":
        """Build a task, its subtasks and its project declaration.

        ``projects=None`` derives the declaration from the images given. That is
        not the auto-extend the design rejects: at creation there is no existing
        declaration to widen and no collaborator to evict. Passing an explicit
        list is stricter -- any image outside it is refused by
        ``fk_SubTaskImageLink_TaskProject``.

        Raises:
            ValueError: if the declaration would be empty. A task declaring
                nothing is visible to every authenticated user *and* cannot
                accept an image, because every image would be outside its
                declaration -- and nothing in this codebase can undo that state.
        """
        from eyened_orm import ImageInstance as _ImageInstance

        # Deriving the declaration needs a second pass over ``imagesets``; a
        # generator argument would otherwise yield subtasks with images and a
        # declaration of nothing.
        materialised = [list(imset) for imset in imagesets]
        subtasks = [SubTask.create_from_images(imset) for imset in materialised]

        if projects is None:
            # Reads the denormalized ImageInstance.ProjectID, so an image that
            # is itself still pending contributes nothing. Callers pass ids or
            # persistent instances; that is the contract.
            image_ids = [
                im.ImageInstanceID if isinstance(im, _ImageInstance) else im
                for imset in materialised
                for im in imset
            ]
            projects = (
                set(
                    session.scalars(
                        select(_ImageInstance.ProjectID).where(
                            _ImageInstance.ImageInstanceID.in_(image_ids)
                        )
                    ).all()
                )
                if image_ids
                else set()
            )

        projects = set(projects)
        if not projects:
            raise ValueError(
                "a task must declare at least one project: pass projects=[...], "
                "or imagesets containing images whose project can be resolved"
            )

        creator = None
        if creator_name is not None:
            from eyened_orm import Creator

            creator = Creator.by_name(session, creator_name)

        taskdef = TaskDefinition.by_name(session, taskdef_name)
        if taskdef is None:
            taskdef = TaskDefinition(TaskDefinitionName=taskdef_name)

        return cls(
            TaskName=task_name,
            TaskDefinition=taskdef,
            TaskState=TaskState.NotStarted,
            SubTasks=subtasks,
            Creator=creator,
            TaskProjects=[TaskProject(ProjectID=pid) for pid in sorted(projects)],
        )

    def get_form_annotations(self, schema_id: Optional[int] = None) -> List["FormAnnotation"]:
        """Return all FormAnnotations for this task; filter by schema if provided."""
        from eyened_orm import FormAnnotation, SubTask

        session = self.session
        q = select(FormAnnotation).join(SubTask).where(SubTask.TaskID == self.TaskID)
        if schema_id is not None:
            q = q.where(FormAnnotation.FormSchemaID == schema_id)

        return session.scalars(q).all()


class SubTaskImageLink(Base):
    """An image inside a subtask, and the point where containment is enforced.

    ``(TaskID, ProjectID)`` referencing ``TaskProject`` is what makes a task's
    declaration binding: an image from a project the task has not declared
    cannot be linked by any writer -- service, script, or raw SQL -- because
    the database refuses the row.
    """

    __tablename__ = "SubTaskImageLink"
    __table_args__ = (
        # (ImageInstanceID, ProjectID) and (SubTaskID, TaskID) lead their
        # indexes because each backs a foreign key. SubTaskID therefore sits
        # third, so an (image, subtask) lookup is no longer a two-column index
        # seek but a seek plus a residual scan -- not measurable, because an
        # equality on ImageInstanceID leaves only a handful of rows.
        Index(
            "ix_SubTaskImageLink_Image_Project",
            "ImageInstanceID", "ProjectID", "SubTaskID",
        ),
        Index("ix_SubTaskImageLink_SubTask_Task", "SubTaskID", "TaskID"),
        Index("ix_SubTaskImageLink_Task_Project", "TaskID", "ProjectID"),
        UniqueConstraint(
            "SubTaskID", "ImageIndex", name="uq_SubTaskImageLink_SubTask_ImageIndex"
        ),
        ForeignKeyConstraint(
            ["SubTaskID", "TaskID"],
            ["SubTask.SubTaskID", "SubTask.TaskID"],
            name="fk_SubTaskImageLink_SubTask_Task",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["ImageInstanceID", "ProjectID"],
            ["ImageInstance.ImageInstanceID", "ImageInstance.ProjectID"],
            name="fk_SubTaskImageLink_Image_Project",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        # No onupdate and no ondelete, deliberately: either would let a change
        # to TaskProject silently rewrite or drop link rows. The point is that
        # a declaration cannot move out from under the links relying on it.
        ForeignKeyConstraint(
            ["TaskID", "ProjectID"],
            ["TaskProject.TaskID", "TaskProject.ProjectID"],
            name="fk_SubTaskImageLink_TaskProject",
        ),
    )
    SubTaskID: Mapped[int] = mapped_column(primary_key=True)
    ImageInstanceID: Mapped[int] = mapped_column(primary_key=True)
    ImageIndex: Mapped[int]
    # Denormalized from SubTask and ImageInstance respectively. Neither is a
    # cache: the composite foreign keys above hold both equal to their source,
    # and the pair is what the containment constraint checks against
    # TaskProject.
    TaskID: Mapped[int]
    ProjectID: Mapped[int]

    SubTask: Mapped["SubTask"] = relationship(
        "eyened_orm.task.SubTask", back_populates="SubTaskImageLinks"
    )
    ImageInstance: Mapped["ImageInstance"] = relationship(
        "eyened_orm.image_instance.ImageInstance", back_populates="SubTaskImageLinks"
    )


class SubTask(Base):
    __tablename__ = "SubTask"
    __table_args__ = (
        Index("fk_SubTask_Creator1_idx", "CreatorID"),
        Index("fk_SubTask_Task1_idx", "TaskID"),
        Index("ix_SubTask_TaskState_Creator", "TaskState", "CreatorID"),
        # Redundant as a uniqueness claim -- SubTaskID alone is the primary
        # key -- but InnoDB will not let SubTaskImageLink's composite foreign
        # key reference (SubTaskID, TaskID) unless that exact pair is a key.
        UniqueConstraint("SubTaskID", "TaskID", name="uq_SubTask_SubTask_Task"),
    )

    SubTaskID: Mapped[int] = mapped_column(primary_key=True)
    TaskID: Mapped[int] = mapped_column(ForeignKey("Task.TaskID", ondelete="CASCADE"))
    CreatorID: Mapped[Optional[int]] = mapped_column(ForeignKey("Creator.CreatorID"))
    Comments: Mapped[Optional[str]] = mapped_column(Text)
    TaskState: Mapped["SubTaskState"] = mapped_column(default=SubTaskState.NotStarted)

    Task: Mapped["Task"] = relationship(
        "eyened_orm.task.Task", back_populates="SubTasks"
    )
    Creator: Mapped[Optional["Creator"]] = relationship(
        "eyened_orm.creator.Creator", back_populates="SubTasks"
    )
    SubTaskImageLinks: Mapped[List["SubTaskImageLink"]] = relationship(
        "eyened_orm.task.SubTaskImageLink",
        back_populates="SubTask",
        passive_deletes=True,
        order_by="SubTaskImageLink.ImageIndex",
    )
    FormAnnotations: Mapped[List["FormAnnotation"]] = relationship(
        "eyened_orm.form_annotation.FormAnnotation", back_populates="SubTask"
    )
    Segmentations: Mapped[List["Segmentation"]] = relationship(
        "eyened_orm.segmentation.Segmentation", back_populates="SubTask"
    )

    @classmethod
    def create_from_images(
        cls,
        images: Iterable[int | ImageInstance],
        task_state: SubTaskState | None = None,
    ) -> "SubTask":
        from eyened_orm import ImageInstance
        if task_state is None:
            task_state = SubTaskState.NotStarted

        subtask = cls(TaskState=task_state)
        subtask.SubTaskImageLinks = [
            SubTaskImageLink(
                ImageInstanceID=(
                    image.ImageInstanceID if isinstance(image, ImageInstance) else image
                ),
                ImageIndex=index,
                SubTask=subtask,
            )
            for index, image in enumerate(images)
        ]

        return subtask
