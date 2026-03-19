from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, List, Optional, Iterable

from sqlalchemy import (
    JSON,
    ForeignKey,
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
    _name_column: ClassVar[str] = "TaskDefinitionName"

    TaskDefinitionID: Mapped[int] = mapped_column(primary_key=True)
    TaskDefinitionName: Mapped[str] = mapped_column(String(256))
    TaskConfig: Mapped[dict | None] = mapped_column(JSON)

    Tasks: Mapped[List["Task"]] = relationship(
        "eyened_orm.task.Task", back_populates="TaskDefinition"
    )
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())


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


class Task(Base):
    __tablename__ = "Task"
    __table_args__ = (
        Index("fk_Task_TaskDefinition1_idx", "TaskDefinitionID"),
        Index("ix_Task_Creator_TaskDefinition", "CreatorID", "TaskDefinitionID"),
    )
    _name_column: ClassVar[str] = "TaskName"

    TaskID: Mapped[int] = mapped_column(primary_key=True)
    TaskName: Mapped[str] = mapped_column(String(256))
    Description: Mapped[Optional[str]] = mapped_column(Text)
    CreatorID: Mapped[Optional[int]] = mapped_column(ForeignKey("Creator.CreatorID"))
    ContactID: Mapped[Optional[int]] = mapped_column(ForeignKey("Contact.ContactID"))
    TaskDefinitionID: Mapped[int] = mapped_column(
        ForeignKey("TaskDefinition.TaskDefinitionID")
    )
    # TaskStateID: Mapped[Optional[int]] = mapped_column(ForeignKey("TaskState.TaskStateID"))

    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

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

    @classmethod
    def create_from_imagesets(
        cls: "Task",
        session: Session,
        taskdef_name: str,
        task_name: str,
        imagesets: Iterable[Iterable[int | ImageInstance]],
        creator_name: str | None = None,
    ) -> "Task":

        subtasks = [SubTask.create_from_images(imset) for imset in imagesets]

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
    __tablename__ = "SubTaskImageLink"
    __table_args__ = (
        Index("fk_SubTaskImageLink_SubTask1_idx", "SubTaskID"),
        Index("fk_SubTaskImageLink_ImageInstance1_idx", "ImageInstanceID"),
        Index(
            "ix_SubTaskImageLink_Image_SubTask",
            "ImageInstanceID",
            "SubTaskID",
        ),
        UniqueConstraint(
            "SubTaskID", "ImageIndex", name="uq_SubTaskImageLink_SubTask_ImageIndex"
        ),
    )
    SubTaskID: Mapped[int] = mapped_column(
        ForeignKey("SubTask.SubTaskID", ondelete="CASCADE"), primary_key=True
    )
    ImageInstanceID: Mapped[int] = mapped_column(
        ForeignKey("ImageInstance.ImageInstanceID", ondelete="CASCADE"),
        primary_key=True,
    )
    ImageIndex: Mapped[int]

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
