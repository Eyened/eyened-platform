"""ORM aliases used by the search query builders.

Pure SQLAlchemy constructs, no UI vocabulary. They live here (rather than in
``server/services/search/fields``) because the repository partitions conditions
by comparing ``entity_of(attr)`` against these alias objects **by identity**, and
``orm/`` may not import ``server/`` -- so there must be exactly one definition and
it must sit at or below the repository. ``fields.py`` imports them from here.
"""
from __future__ import annotations

from eyened_orm import Creator, FormAnnotation, Segmentation, Tag
from sqlalchemy import select
from sqlalchemy.orm import aliased

ActiveSegmentation = aliased(
    Segmentation,
    select(Segmentation)
    .filter(~Segmentation.Inactive)
    .subquery(name="active_segmentation"),
    name="active_segmentation",
)
ActiveFormAnnotation = aliased(
    FormAnnotation,
    select(FormAnnotation)
    .filter(~FormAnnotation.Inactive)
    .subquery(name="active_form_annot"),
    name="active_form_annot",
)
SegCreator = aliased(Creator, name="seg_creator")
FormCreator = aliased(Creator, name="form_creator")
SegTag = aliased(Tag, name="seg_tag")
FormTag = aliased(Tag, name="form_tag")
InstTag = aliased(Tag, name="image_tag")
StudyTag = aliased(Tag, name="study_tag")
