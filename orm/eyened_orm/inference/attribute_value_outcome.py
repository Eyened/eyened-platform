"""AttributeValue success/failure detection without a dedicated Succeeded column.

Convention (until ``AttributeValue.Succeeded`` exists):
- **No row** — not yet attempted
- **Row with a non-null value column** — succeeded
- **Row with all value columns null** — failed attempt (recorded, skip on re-run)

When a ``Succeeded`` column is added later, update :func:`attribute_value_outcome`
only; callers stay unchanged.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from eyened_orm import AttributeDataType

if TYPE_CHECKING:
    from eyened_orm import AttributeValue


class AttributeValueOutcome(str, Enum):
    MISSING = "missing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


VALUE_COLUMNS: tuple[str, ...] = (
    "ValueJSON",
    "ValueFloat",
    "ValueInt",
    "ValueText",
)

VALUE_COLUMN_BY_DATA_TYPE: dict[AttributeDataType, str] = {
    AttributeDataType.JSON: "ValueJSON",
    AttributeDataType.Float: "ValueFloat",
    AttributeDataType.Int: "ValueInt",
    AttributeDataType.String: "ValueText",
}


def value_column_for_data_type(data_type: AttributeDataType) -> str:
    try:
        return VALUE_COLUMN_BY_DATA_TYPE[data_type]
    except KeyError:
        return "ValueJSON"


def has_stored_value(av: AttributeValue) -> bool:
    """True when any value column is non-null."""
    return any(getattr(av, column) is not None for column in VALUE_COLUMNS)


def attribute_value_outcome(av: AttributeValue | None) -> AttributeValueOutcome:
    """Classify an AttributeValue row for pipeline skip/retry logic."""
    if av is None:
        return AttributeValueOutcome.MISSING

    # Future: dedicated column takes precedence over NULL-value heuristic.
    succeeded_flag = getattr(av, "Succeeded", None)
    if succeeded_flag is True:
        return AttributeValueOutcome.SUCCEEDED
    if succeeded_flag is False:
        return AttributeValueOutcome.FAILED

    if has_stored_value(av):
        return AttributeValueOutcome.SUCCEEDED
    return AttributeValueOutcome.FAILED


def is_available_input(av: AttributeValue) -> bool:
    """True when an AttributeValue can be consumed as a model input."""
    return attribute_value_outcome(av) == AttributeValueOutcome.SUCCEEDED


def success_update_values(data_type: AttributeDataType, value: Any) -> dict[str, Any]:
    """Build upsert kwargs for a successful inference result."""
    column = value_column_for_data_type(data_type)
    return {column: value, **{col: None for col in VALUE_COLUMNS if col != column}}


def failure_update_values() -> dict[str, Any]:
    """Build upsert kwargs for a failed inference attempt (all value columns null)."""
    return {column: None for column in VALUE_COLUMNS}


def image_ids_with_recorded_outcome(
    attribute_values: list[AttributeValue],
) -> set[int]:
    """Image IDs that already have a succeeded or failed AttributeValue row."""
    return {
        av.ImageInstanceID
        for av in attribute_values
        if av.ImageInstanceID is not None
        and attribute_value_outcome(av) != AttributeValueOutcome.MISSING
    }


def image_ids_with_succeeded_outcome(
    attribute_values: list[AttributeValue],
) -> set[int]:
    """Image IDs that already have a succeeded AttributeValue row."""
    return {
        av.ImageInstanceID
        for av in attribute_values
        if av.ImageInstanceID is not None
        and attribute_value_outcome(av) == AttributeValueOutcome.SUCCEEDED
    }


def image_ids_with_failed_outcome(
    attribute_values: list[AttributeValue],
) -> set[int]:
    """Image IDs that have a failed AttributeValue row (null value columns)."""
    return {
        av.ImageInstanceID
        for av in attribute_values
        if av.ImageInstanceID is not None
        and attribute_value_outcome(av) == AttributeValueOutcome.FAILED
    }
