from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKeyConstraint, Index, String, UniqueConstraint, select
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
        # The parent half of ImageInstance's composite foreign key -- see the
        # equivalent on Patient.
        UniqueConstraint("SeriesID", "ProjectID", name="uq_Series_Series_Project"),
        # Declared rather than left to InnoDB, which would create the
        # referencing-side index itself under a generated name no later
        # migration can predict or drop. Additional to the ForeignKeyIndex
        # above, which stays: that one indexes StudyID alone.
        Index("ix_Series_Study_Project", "StudyID", "ProjectID"),
        # This REPLACES the single-column FK that used to sit on StudyID -- see
        # the equivalent on Study for why it cannot be added alongside it.
        ForeignKeyConstraint(
            ["StudyID", "ProjectID"],
            ["Study.StudyID", "Study.ProjectID"],
            name="fk_Series_Study_Project",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )
    SeriesID: Mapped[int] = mapped_column(primary_key=True)

    # No column-level ForeignKey: the key on this column is the composite in
    # __table_args__ above.
    StudyID: Mapped[int]
    # Denormalized from Patient.ProjectID by way of Study, held equal to Study's
    # own copy by the composite foreign key above; also populated by the
    # before_flush listener in authz/denormalization.py, which covers the
    # writers foreign-key sync never fires for. Deliberately no single-column
    # ForeignKey to Project: a second path straight to Project would let the two
    # disagree about which project this series is in.
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
