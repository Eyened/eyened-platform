from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, func, select, Text
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from eyened_orm.base import Base, ForeignKeyIndex

from .form_annotation import FormAnnotation

if TYPE_CHECKING:
    from .image_instance import ImageInstance    
    from .project import Contact
    from .annotation import Creator


class TaskDefinition(Base):
    __tablename__ = "TaskDefinition"
    TaskDefinitionID: Mapped[int] = mapped_column(primary_key=True)

    TaskDefinitionName: Mapped[str] = mapped_column(String(256))

    Tasks: Mapped[List[Task]] = relationship("eyened_orm.task.Task", back_populates="TaskDefinition")

    # datetimes
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    @classmethod
    def by_name(cls, session: Session, name):
        return session.scalar(
            select(TaskDefinition).where(TaskDefinition.TaskDefinitionName == name)
        )

    def __repr__(self):
        return f"TaskDefinition({self.TaskDefinitionID}, {self.TaskDefinitionName}, {self.DateInserted})"


class TaskState(Base):
    __tablename__ = "TaskState"
    TaskStateID: Mapped[int] = mapped_column(primary_key=True)

    TaskStateName: Mapped[str] = mapped_column(String(256))

    Tasks: Mapped[List[Task]] = relationship("eyened_orm.task.Task", back_populates="TaskState")
    SubTasks: Mapped[List[SubTask]] = relationship("eyened_orm.task.SubTask", back_populates="TaskState")

    @classmethod
    def by_name(cls, session: Session, name: str):
        return session.scalar(select(TaskState).where(TaskState.TaskStateName == name))

    def __repr__(self):
        return f"TaskState({self.TaskStateID}, {self.TaskStateName})"


class Task(Base):
    __tablename__ = "Task"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "TaskDefinition", "TaskDefinitionID"),
        ForeignKeyIndex(__tablename__, "TaskState", "TaskStateID"),
    )
    TaskID: Mapped[int] = mapped_column(primary_key=True)

    TaskName: Mapped[str] = mapped_column(String(256))
    Description: Mapped[Optional[str]] = mapped_column(Text)

    ## Contact
    ContactID: Mapped[Optional[int]] = mapped_column(ForeignKey("Contact.ContactID"))
    Contact: Mapped[Optional[Contact]] = relationship("eyened_orm.project.Contact", back_populates="Tasks")

    TaskDefinitionID: Mapped[int] = mapped_column(
        ForeignKey(TaskDefinition.TaskDefinitionID)
    )
    TaskDefinition: Mapped[TaskDefinition] = relationship("eyened_orm.task.TaskDefinition", back_populates="Tasks")

    TaskStateID: Mapped[int] = mapped_column(ForeignKey(TaskState.TaskStateID), 
                                             nullable=True)
    TaskState: Mapped[TaskState] = relationship("eyened_orm.task.TaskState", back_populates="Tasks")

    SubTasks: Mapped[List[SubTask]] = relationship("eyened_orm.task.SubTask", back_populates="Task")
    
    # datetimes
    DateInserted: Mapped[datetime] = mapped_column(server_default=func.now())

    @classmethod
    def by_name(cls, session: Session, name: str):
        return session.scalar(select(Task).where(Task.TaskName == name))

    @classmethod
    def create_from_imagesets(
        cls: Task,
        session: Session,
        taskdef_name: str,
        task_name: str,
        imagesets: List[List[int]],
        creator_name=None,
    ) -> Task:
        from .annotation import Creator

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

    def get_form_annotations(self, session: Session, schema_id: int = None):
        """
        Returns all FormAnnotations for this task.
        If schema_id is provided, only returns FormAnnotations for that schema.
        """
        q = select(FormAnnotation).join(SubTask).where(SubTask.TaskID == self.TaskID)
        if schema_id is not None:
            q = q.where(FormAnnotation.FormSchemaID == schema_id)

        return session.execute(q).all()

    def __repr__(self):
        return f"Task({self.TaskID}, {self.TaskName}, {self.TaskDefinition}, {self.TaskState}, {self.DateInserted})"


class SubTaskImageLink(Base):
    __tablename__ = "SubTaskImageLink"
    __table_args__ = (
        ForeignKeyIndex("SubTaskImageLink", "SubTask", "SubTaskID"),
        ForeignKeyIndex("SubTaskImageLink", "ImageInstance", "ImageInstanceID"),
    )

    SubTaskImageLinkID: Mapped[int] = mapped_column(primary_key=True)
    SubTaskID: Mapped[int] = mapped_column(ForeignKey("SubTask.SubTaskID"))
    SubTask: Mapped[SubTask] = relationship("eyened_orm.task.SubTask", back_populates="SubTaskImageLinks")
    ImageInstanceID: Mapped[int] = mapped_column(
        ForeignKey("ImageInstance.ImageInstanceID")
    )
    ImageInstance: Mapped[ImageInstance] = relationship(
        "eyened_orm.image_instance.ImageInstance", back_populates="SubTaskImageLinks"
    )


class SubTask(Base):
    __tablename__ = "SubTask"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Creator", "CreatorID"),
        ForeignKeyIndex(__tablename__, "Task", "TaskID"),
        ForeignKeyIndex(__tablename__, "TaskState", "TaskStateID"),
    )

    SubTaskID: Mapped[int] = mapped_column(primary_key=True)

    TaskID: Mapped[int] = mapped_column(ForeignKey(Task.TaskID))
    Task: Mapped[Task] = relationship("eyened_orm.task.Task", back_populates="SubTasks")

    TaskStateID: Mapped[int] = mapped_column(ForeignKey(TaskState.TaskStateID))
    TaskState: Mapped[TaskState] = relationship("eyened_orm.task.TaskState", back_populates="SubTasks")

    CreatorID: Mapped[Optional[int]] = mapped_column(ForeignKey("Creator.CreatorID"))
    Creator: Mapped[Optional[Creator]] = relationship("eyened_orm.creator.Creator", back_populates="SubTasks")

    SubTaskImageLinks: Mapped[List[SubTaskImageLink]] = relationship(
        "eyened_orm.task.SubTaskImageLink", back_populates="SubTask"
    )

    FormAnnotations: Mapped[List[FormAnnotation]] = relationship(
        "eyened_orm.form_annotation.FormAnnotation", back_populates="SubTask"
    )

    @classmethod
    def create_from_image_ids(
        cls, session: Session, image_ids: List[int], task_state: str = None
    ):
        if task_state is None:
            task_state = "Not Started"

        subtask = cls(TaskState=TaskState.by_name(session, task_state))
        subtask.SubTaskImageLinks = [
            SubTaskImageLink(ImageInstanceID=id, SubTask=subtask) for id in image_ids
        ]

        return subtask
