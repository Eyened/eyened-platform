import datetime
from typing import TYPE_CHECKING, List, Optional, Set

from sqlalchemy import (
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from eyened_orm import (
        Annotation,
        AttributeValue,
        FormAnnotation,
        ImageInstance,
        Patient,
        Series,
        StudyTagLink,
    )


class Study(Base):
    """A visit (study) of a patient; groups images taken on the same day."""

    __tablename__ = "Study"
    __table_args__ = (
        Index("PatientIDStudyDate_UNIQUE", "PatientID", "StudyDate", unique=True),
        Index("StudyDate_idx", "StudyDate"),
        Index("fk_Study_Patient1_idx", "PatientID"),
        Index("ix_Study_PatientID_StudyRound", "PatientID", "StudyRound"),
        Index("ix_Study_StudyRound_StudyDate", "StudyRound", "StudyDate"),
        # The parent half of Series' composite foreign key -- see the
        # equivalent on Patient.
        UniqueConstraint("StudyID", "ProjectID", name="uq_Study_Study_Project"),
        # Declared rather than left to InnoDB, which would create the
        # referencing-side index itself under a generated name no later
        # migration can predict or drop.
        Index("ix_Study_Patient_Project", "PatientID", "ProjectID"),
        # This REPLACES the single-column FK on PatientID rather than joining
        # it: two foreign-key paths between Study and Patient make SQLAlchemy
        # refuse to configure Study.Patient at all (AmbiguousForeignKeysError).
        # The composite is also what makes the ORM copy ProjectID
        # parent-to-child on flush.
        #
        # ondelete is required because Patient.Studies is passive_deletes=True,
        # which leaves the cascade to the database. onupdate is what holds the
        # denormalized copy equal to its parent when a patient moves project.
        ForeignKeyConstraint(
            ["PatientID", "ProjectID"],
            ["Patient.PatientID", "Patient.ProjectID"],
            name="fk_Study_Patient_Project",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )

    StudyID: Mapped[int] = mapped_column(primary_key=True)
    # No column-level ForeignKey: the key on this column is the composite in
    # __table_args__ above.
    PatientID: Mapped[int]
    # Denormalized from Patient.ProjectID and held equal to it by the composite
    # foreign key above; also populated by the before_flush listener in
    # authz/denormalization.py, which covers the writers foreign-key sync never
    # fires for. Deliberately no single-column ForeignKey to Project: a second
    # path straight to Project would let the two disagree about which project
    # this study is in.
    ProjectID: Mapped[int]
    StudyRound: Mapped[Optional[int]]
    StudyDescription: Mapped[Optional[str]] = mapped_column(String(64))
    StudyDate: Mapped[datetime.date]

    DateInserted: Mapped[datetime.datetime] = mapped_column(server_default=func.current_timestamp())

    Patient: Mapped["Patient"] = relationship(
        "eyened_orm.patient.Patient", back_populates="Studies", lazy="selectin"
    )
    Series: Mapped[List["Series"]] = relationship(
        "eyened_orm.series.Series",
        back_populates="Study",
        passive_deletes=True,
        lazy="selectin",
    )
    Annotations: Mapped[List["Annotation"]] = relationship(
        "eyened_orm.annotation.Annotation", back_populates="Study"
    )
    FormAnnotations: Mapped[List["FormAnnotation"]] = relationship(
        "eyened_orm.form_annotation.FormAnnotation", back_populates="Study"
    )
    AttributeValues: Mapped[List["AttributeValue"]] = relationship(
        "eyened_orm.attributes.AttributeValue", back_populates="Study"
    )
    StudyTagLinks: Mapped[Set["StudyTagLink"]] = relationship(
        "eyened_orm.tag.StudyTagLink", back_populates="Study", lazy="selectin"
    )

    @classmethod
    def by_patient_and_date(
        cls, session: Session, patient_id: int, study_date: datetime.date
    ) -> Optional["Study"]:
        return session.scalar(
            select(Study).where(
                Study.PatientID == patient_id, Study.StudyDate == study_date
            )
        )

    @property
    def age_years(self) -> float | None:
        if self.StudyDate is None or self.Patient.BirthDate is None:
            return None
        return (self.StudyDate - self.Patient.BirthDate).days / 365.25

    @property
    def images(self) -> List["ImageInstance"]:
        return self.get_images()

    def get_images(self, where=None, include_inactive=False) -> List["ImageInstance"]:
        from eyened_orm import ImageInstance, Series

        q = select(ImageInstance).join(Series).where(Series.StudyID == self.StudyID)
        if not include_inactive:
            q = q.where(~ImageInstance.Inactive)
        if where is not None:
            q = q.where(where)
        session = Session.object_session(self)
        return session.scalars(q).all()

    def make_tag(
        self,
        tag_name: str,
        creator_name: str,
        comment: Optional[str] = None,
        tag_description: Optional[str] = None,
    ) -> "StudyTagLink":
        """Create or reuse a tag and link it to this study."""
        from eyened_orm import Creator, Tag, TagType
        from eyened_orm.tag import StudyTagLink

        session = self.session
        tag_type = TagType.Study

        # Get or create creator
        creator = Creator.by_name(session, creator_name)
        if creator is None:
            creator = Creator(CreatorName=creator_name, IsHuman=True)
            session.add(creator)
            session.flush()

        # Get or create tag
        tag = Tag.by_column(session, TagName=tag_name, TagType=tag_type)
        if tag is None:
            if tag_description is None:
                raise ValueError(
                    f"Tag '{tag_name}' does not exist and tag_description is required for new tags"
                )
            tag = Tag(
                TagName=tag_name,
                TagType=tag_type,
                TagDescription=tag_description,
                CreatorID=creator.CreatorID,
            )
            session.add(tag)
            session.flush()
        elif tag_description is not None and tag.TagDescription != tag_description:
            raise ValueError(
                f"Tag '{tag_name}' exists with different description: '{tag.TagDescription}' != '{tag_description}'"
            )

        # Get or create link
        link = StudyTagLink.by_pk(session, (tag.TagID, self.StudyID))
        if link is None:
            link = StudyTagLink(
                TagID=tag.TagID,
                StudyID=self.StudyID,
                CreatorID=creator.CreatorID,
                Comment=comment,
            )
            session.add(link)
            session.flush()
        elif comment is not None:
            link.Comment = comment
            session.flush()

        return link
