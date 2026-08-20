from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Index, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base, ForeignKeyIndex

if TYPE_CHECKING:
    from eyened_orm import Annotation, ImageInstance, Study


class Series(Base):
    __tablename__ = "Series"
    __table_args__ = (
        ForeignKeyIndex(__tablename__, "Study", "StudyID"),
        Index(
            "StudyInstanceUidSeriesInstanceUid_UNIQUE",
            "StudyInstanceUid",
            "SeriesInstanceUid",
            unique=True,
        ),
        Index("ix_Series_StudyID_SeriesNumber", "StudyID", "SeriesNumber"),
        Index("ix_Series_StudyID_StudyInstanceUid", "StudyID", "StudyInstanceUid"),
    )
    SeriesID: Mapped[int] = mapped_column(primary_key=True)

    StudyID: Mapped[int] = mapped_column(
        ForeignKey("Study.StudyID", ondelete="CASCADE")
    )
    # The project that the series belongs to, denormalized from
    # Patient.ProjectID by way of Study. Populated by the before_flush and
    # before_insert listeners in authz/denormalization.py -- see that module's
    # docstring for which writer needs which.
    #
    # Deliberately no ForeignKey to Project here: the value is meant to be held
    # equal to the parent Study's own copy by a composite foreign key, and a
    # second single-column FK straight to Project would let the two disagree
    # about which project this series is in.
    ProjectID: Mapped[int]

    SeriesNumber: Mapped[Optional[int]] = mapped_column()
    SeriesInstanceUid: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    StudyInstanceUid: Mapped[Optional[str]] = mapped_column(String(64))

    Study: Mapped[Study] = relationship(
        "eyened_orm.study.Study", back_populates="Series", lazy="selectin"
    )
    ImageInstances: Mapped[List[ImageInstance]] = relationship(
        "eyened_orm.image_instance.ImageInstance",
        back_populates="Series",
        cascade="all,delete-orphan",
        lazy="selectin",
    )
    Annotations: Mapped[List[Annotation]] = relationship(
        "eyened_orm.annotation.Annotation", back_populates="Series"
    )

    def __repr__(self):
        return f"Series({self.SeriesID}, {self.SeriesNumber}, {self.SeriesInstanceUid})"

    def get_images(self, where=None) -> List[ImageInstance]:
        session = Session.object_session(self)
        q = (
            select(ImageInstance)
            .join_from(ImageInstance, Series)
            .where(~ImageInstance.Inactive)
            .where(Series.SeriesID == self.SeriesID)
        )
        if where is not None:
            q = q.where(where)
        return session.scalars(q)
