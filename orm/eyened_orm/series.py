from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base, ForeignKeyIndex

if TYPE_CHECKING:
    from eyened_orm import Annotation, ImageInstance, Study


class Series(Base):
    __tablename__ = "Series"
    __table_args__ = (ForeignKeyIndex(__tablename__, "Study", "StudyID"),)
    SeriesID: Mapped[int] = mapped_column(primary_key=True)

    
    StudyID: Mapped[int] = mapped_column(
        ForeignKey("Study.StudyID", ondelete="CASCADE")
    )
    

    SeriesNumber: Mapped[Optional[int]] = mapped_column()
    SeriesInstanceUid: Mapped[Optional[str]] = mapped_column(String(64), unique=True)


    Study: Study = relationship("eyened_orm.study.Study", back_populates="Series")
    ImageInstances: List[ImageInstance] = relationship(
        "eyened_orm.image_instance.ImageInstance",
        back_populates="Series", cascade="all,delete-orphan"
    )
    Annotations: List[Annotation] = relationship("eyened_orm.annotation.Annotation", back_populates="Series")

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
