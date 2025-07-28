from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, List, Optional

from sqlalchemy import JSON, Column, Index, Text, select
from sqlalchemy.orm import Session
from sqlmodel import Field, Relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import (
        Contact,
        Creator,
        FormAnnotation,
        ImageInstance,
        SubTask,
        TaskDefinition,
        TaskState,
        Segmentation,
    )


class TaskDefinitionBase(Base):
    TaskDefinitionName: str = Field(max_length=256)
    TaskConfig: dict | None = Field(sa_column=Column(JSON), default=None)


class TaskStateBase(Base):
    TaskStateName: str = Field(max_length=256, unique=True)


class TaskDefinition(TaskDefinitionBase, table=True):
    __tablename__ = "TaskDefinition"
    _name_column: ClassVar[str] = "TaskDefinitionName"

    TaskDefinitionID: int = Field(primary_key=True)

    Tasks: List["Task"] = Relationship(back_populates="TaskDefinition")
    DateInserted: datetime = Field(default_factory=datetime.now)


class TaskState(TaskStateBase, table=True):
    __tablename__ = "TaskState"

    _name_column: ClassVar[str] = "TaskStateName"

    TaskStateID: int = Field(primary_key=True)

    Tasks: List["Task"] = Relationship(back_populates="TaskState")
    SubTasks: List["SubTask"] = Relationship(back_populates="TaskState")


class TaskBase(Base):
    TaskName: str = Field(max_length=256)
    Description: str | None = Field(sa_column=Column(Text))
    ContactID: int | None = Field(foreign_key="Contact.ContactID", default=None)
    TaskDefinitionID: int = Field(foreign_key="TaskDefinition.TaskDefinitionID")
    TaskStateID: int | None = Field(foreign_key="TaskState.TaskStateID", default=None)


class Task(TaskBase, table=True):
    __tablename__ = "Task"
    __table_args__ = (
        Index("fk_Task_TaskDefinition1_idx", "TaskDefinitionID"),
        Index("fk_Task_TaskState1_idx", "TaskStateID"),
    )
    _name_column: ClassVar[str] = "TaskName"

    TaskID: int = Field(primary_key=True)
    DateInserted: datetime = Field(default_factory=datetime.now)

    Contact: Optional["Contact"] = Relationship(back_populates="Tasks")
    TaskDefinition: "TaskDefinition" = Relationship(back_populates="Tasks")
    TaskState: "TaskState" = Relationship(back_populates="Tasks")
    SubTasks: List["SubTask"] = Relationship(back_populates="Task")

    @classmethod
    def create_from_imagesets(
        cls: "Task",
        session: Session,
        taskdef_name: str,
        task_name: str,
        imagesets: List[List[int]],
        creator_name: str | None = None,
    ) -> "Task":
        from .Annotation import Creator

        subtasks = [
            SubTask.create_from_image_ids(session, imset) for imset in imagesets
        ]
        state = TaskState.by_name(session, "Not Started")

        if creator_name is not None:
            creator = Creator.by_name(session, creator_name)
            for subtask in subtasks:
                subtask.Creator = creator
        taskdef = TaskDefinition.by_name(session, taskdef_name)

        return cls(
            TaskName=task_name,
            TaskDefinition=taskdef,
            TaskState=state,
            SubTasks=subtasks,
        )

    def get_form_annotations(
        self, session: Session, schema_id: Optional[int] = None
    ) -> List["FormAnnotation"]:
        """
        Returns all FormAnnotations for this task.
        If schema_id is provided, only returns FormAnnotations for that schema.
        """
        q = select(FormAnnotation).join(SubTask).where(SubTask.TaskID == self.TaskID)
        if schema_id is not None:
            q = q.where(FormAnnotation.FormSchemaID == schema_id)

        return session.scalars(q).all()


class SubTaskImageLink(Base, table=True):
    __tablename__ = "SubTaskImageLink"
    __table_args__ = (
        Index("fk_SubTaskImageLink_SubTask1_idx", "SubTaskID"),
        Index("fk_SubTaskImageLink_ImageInstance1_idx", "ImageInstanceID"),
    )
    SubTaskID: int = Field(foreign_key="SubTask.SubTaskID", primary_key=True)
    ImageInstanceID: int = Field(
        foreign_key="ImageInstance.ImageInstanceID", primary_key=True
    )

    SubTask: "SubTask" = Relationship(back_populates="SubTaskImageLinks")
    ImageInstance: "ImageInstance" = Relationship(back_populates="SubTaskImageLinks")


class SubTaskBase(Base):
    TaskID: int = Field(foreign_key="Task.TaskID")
    TaskStateID: int = Field(foreign_key="TaskState.TaskStateID")
    CreatorID: int | None = Field(foreign_key="Creator.CreatorID", default=None)
    Comments: str | None = Field(sa_column=Column(Text), default=None)


class SubTask(SubTaskBase, table=True):
    __tablename__ = "SubTask"
    __table_args__ = (
        Index("fk_SubTask_Creator1_idx", "CreatorID"),
        Index("fk_SubTask_Task1_idx", "TaskID"),
        Index("fk_SubTask_TaskState1_idx", "TaskStateID"),
    )

    SubTaskID: int = Field(primary_key=True)

    Task: "Task" = Relationship(back_populates="SubTasks")
    TaskState: "TaskState" = Relationship(back_populates="SubTasks")
    Creator: Optional["Creator"] = Relationship(back_populates="SubTasks")
    SubTaskImageLinks: List["SubTaskImageLink"] = Relationship(back_populates="SubTask")
    FormAnnotations: List["FormAnnotation"] = Relationship(back_populates="SubTask")
    Segmentations: List["Segmentation"] = Relationship(back_populates="SubTask")

    @classmethod
    def create_from_image_ids(
        cls, session: Session, image_ids: List[int], task_state: str | None = None
    ) -> "SubTask":
        if task_state is None:
            task_state = "Not Started"

        subtask = cls(TaskState=TaskState.by_name(session, task_state))
        subtask.SubTaskImageLinks = [
            SubTaskImageLink(ImageInstanceID=id, SubTask=subtask) for id in image_ids
        ]

        return subtask
