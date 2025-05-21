from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Column, select, Text, Index
from sqlalchemy.orm import Session
from sqlmodel import Field, Relationship

from .FormAnnotation import FormAnnotation
from .base import Base
if TYPE_CHECKING:
    from .ImageInstance import ImageInstance    
    from .Project import Contact
    from .Annotation import Creator


class TaskDefinition(Base, table=True):
    __tablename__ = "TaskDefinition"
    TaskDefinitionID: int = Field(primary_key=True)
    TaskDefinitionName: str = Field(max_length=256)

    Tasks: List["Task"] = Relationship(back_populates="TaskDefinition")

    # datetimes
    DateInserted: datetime = Field(default_factory=datetime.now)

    @classmethod
    def by_name(cls, session: Session, name: str) -> Optional["TaskDefinition"]:
        return session.scalar(
            select(TaskDefinition).where(TaskDefinition.TaskDefinitionName == name)
        )

    def __repr__(self):
        return f"TaskDefinition({self.TaskDefinitionID}, {self.TaskDefinitionName}, {self.DateInserted})"


class TaskState(Base, table=True):
    __tablename__ = "TaskState"
    TaskStateID: int = Field(primary_key=True)
    TaskStateName: str = Field(max_length=256)

    Tasks: List["Task"] = Relationship(back_populates="TaskState")
    SubTasks: List["SubTask"] = Relationship(back_populates="TaskState")

    @classmethod
    def by_name(cls, session: Session, name: str) -> Optional["TaskState"]:
        return session.scalar(select(TaskState).where(TaskState.TaskStateName == name))

    def __repr__(self):
        return f"TaskState({self.TaskStateID}, {self.TaskStateName})"


class Task(Base, table=True):
    __tablename__ = "Task"
    __table_args__ = (
        Index("fk_Task_TaskDefinition1_idx", "TaskDefinitionID"),
        Index("fk_Task_TaskState1_idx", "TaskStateID"),
    )
    TaskID: int = Field(primary_key=True)

    TaskName: str = Field(max_length=256)
    Description: Optional[str] = Field(default=None, sa_column=Column(Text))

    ## Contact
    ContactID: Optional[int] = Field(default=None, foreign_key="Contact.ContactID")
    Contact: Optional["Contact"] = Relationship(back_populates="Tasks")

    TaskDefinitionID: int = Field(foreign_key="TaskDefinition.TaskDefinitionID")
    TaskDefinition: "TaskDefinition" = Relationship(back_populates="Tasks")

    TaskStateID: Optional[int] = Field(default=None, foreign_key="TaskState.TaskStateID")
    TaskState: "TaskState" = Relationship(back_populates="Tasks")

    SubTasks: List["SubTask"] = Relationship(back_populates="Task")

    # datetimes
    DateInserted: datetime = Field(default_factory=datetime.now)

    @classmethod
    def by_name(cls, session: Session, name: str) -> Optional["Task"]:
        return session.scalar(select(Task).where(Task.TaskName == name))

    @classmethod
    def create_from_imagesets(
        cls: "Task",
        session: Session,
        taskdef_name: str,
        task_name: str,
        imagesets: List[List[int]],
        creator_name: Optional[str] = None,
    ) -> "Task":
        from .Annotation import Creator

        subtasks = [SubTask.create_from_image_ids(session, imset) for imset in imagesets]
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

    def get_form_annotations(self, session: Session, schema_id: Optional[int] = None) -> List["FormAnnotation"]:
        """
        Returns all FormAnnotations for this task.
        If schema_id is provided, only returns FormAnnotations for that schema.
        """
        q = select(FormAnnotation).join(SubTask).where(SubTask.TaskID == self.TaskID)
        if schema_id is not None:
            q = q.where(FormAnnotation.FormSchemaID == schema_id)

        return session.scalars(q).all()

    def __repr__(self):
        return f"Task({self.TaskID}, {self.TaskName}, {self.TaskDefinition}, {self.TaskState}, {self.DateInserted})"


class SubTaskImageLink(Base, table=True):
    __tablename__ = "SubTaskImageLink"
    __table_args__ = (
        Index("fk_SubTaskImageLink_SubTask1_idx", "SubTaskID"),
        Index("fk_SubTaskImageLink_ImageInstance1_idx", "ImageInstanceID"),
    )

    SubTaskImageLinkID: int = Field(primary_key=True)
    SubTaskID: int = Field(foreign_key="SubTask.SubTaskID")
    SubTask: "SubTask" = Relationship(back_populates="SubTaskImageLinks")
    ImageInstanceID: int = Field(foreign_key="ImageInstance.ImageInstanceID")
    ImageInstance: "ImageInstance" = Relationship(back_populates="SubTaskImageLinks")


class SubTask(Base, table=True):
    __tablename__ = "SubTask"
    __table_args__ = (
        Index("fk_SubTask_Creator1_idx", "CreatorID"),
        Index("fk_SubTask_Task1_idx", "TaskID"),
        Index("fk_SubTask_TaskState1_idx", "TaskStateID"),
    )

    SubTaskID: int = Field(primary_key=True)

    TaskID: int = Field(foreign_key="Task.TaskID")
    Task: "Task" = Relationship(back_populates="SubTasks")

    TaskStateID: int = Field(foreign_key="TaskState.TaskStateID")
    TaskState: "TaskState" = Relationship(back_populates="SubTasks")

    CreatorID: Optional[int] = Field(default=None, foreign_key="Creator.CreatorID")
    Creator: Optional["Creator"] = Relationship(back_populates="SubTasks")

    SubTaskImageLinks: List["SubTaskImageLink"] = Relationship(back_populates="SubTask")
    FormAnnotations: List["FormAnnotation"] = Relationship(back_populates="SubTask")

    Comments: str | None = Field(default=None, sa_column=Column(Text))


    @classmethod
    def create_from_image_ids(
        cls, session: Session, image_ids: List[int], task_state: Optional[str] = None
    ) -> "SubTask":
        if task_state is None:
            task_state = "Not Started"

        subtask = cls(TaskState=TaskState.by_name(session, task_state))
        subtask.SubTaskImageLinks = [
            SubTaskImageLink(ImageInstanceID=id, SubTask=subtask) for id in image_ids
        ]

        return subtask
