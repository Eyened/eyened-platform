from typing import Optional, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.sql.elements import ColumnElement

from eyened_orm import AttributeValue, ImageInstance, Study, Series, Patient


def select_top_per_eye(
    *,
    image_ids: Sequence[int],
    model_id: int,
    columns: Sequence[ColumnElement],
    value_col: ColumnElement = AttributeValue.ValueFloat,
    null_as: float = 0,
    tie_breaker: Optional[ColumnElement] = ImageInstance.ImageInstanceID.desc(),
) -> Select:
    """Select the top image instance per eye (study + laterality) for a given model.

    Args:
        image_ids: The image IDs to select from (ImageInstance.ImageInstanceID).
        model_id: The model ID to select from (AttributeModel.ModelID).
        columns: The columns to select from (ImageInstance.ImageInstanceID, ImageInstance.Laterality, etc.).
        value_col: The column to use for the value (AttributeValue.ValueFloat).
        null_as: The value to use for nulls (0).
        tie_breaker: The tie breaker to use (ImageInstance.ImageInstanceID.desc()).

    Returns:
        A select statement.
    """
    # Ensure every returned column is addressable from the subquery via ranked.c.<name>
    labeled = [c.label(f"c{i}") for i, c in enumerate(columns)]

    order_by = (
        (
            func.coalesce(value_col, null_as).desc(),
            tie_breaker,
        )
        if tie_breaker is not None
        else (func.coalesce(value_col, null_as).desc(),)
    )

    ranked = (
        select(
            *labeled,
            func.row_number()
            .over(
                partition_by=(Study.StudyID, ImageInstance.Laterality),
                order_by=order_by,
            )
            .label("rn"),
        )
        .select_from(ImageInstance)
        .join(Series)
        .join(Study)
        .join(Patient)
        .join(
            AttributeValue,
            (AttributeValue.ImageInstanceID == ImageInstance.ImageInstanceID)
            & (AttributeValue.ModelID == model_id),
            isouter=True,
        )
        .where(ImageInstance.ImageInstanceID.in_(image_ids))
    ).subquery()

    return select(*[ranked.c[c.key] for c in labeled]).where(ranked.c.rn == 1)
