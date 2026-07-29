"""Condition carriers and SQLAlchemy-expression construction for search.

The two frozen dataclasses are the repository's typed public boundary:
callers hand in ``ResolvedCondition`` (variable already resolved to an ORM
attribute) and ``AttributeConditionSpec`` (attribute still addressed by name,
resolved against the DB inside the repository). The expression helpers below
(``format_condition``, ``and_expr``, the attribute value coercion, ``entity_of``,
``partition_conditions_by_entity``) are moved verbatim from the old route module
and still operate on plain dicts -- the select builders convert the typed inputs
to dicts at their boundary, which keeps this machinery byte-for-byte unchanged.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from eyened_orm.attributes import AttributeDataType
from eyened_orm.attributes import AttributeDefinition as AttrDef
from eyened_orm.attributes import AttributeValue as AttrVal
from sqlalchemy import and_, true
from sqlalchemy import inspect as sa_inspect


@dataclass(frozen=True)
class ResolvedCondition:
    """One condition whose ``variable`` is already an ORM attribute."""

    variable: Any
    operator: str
    value: Any = None


@dataclass(frozen=True)
class AttributeConditionSpec:
    """One attribute condition, still addressed by name (resolved against the DB here)."""

    attribute: str
    operator: str
    value: Any = None
    model: Optional[str] = None
    feature: Optional[str] = None


def format_condition(variable: Any, condition: Dict[str, Any]) -> Any:
    """Return a SQLAlchemy boolean expression for one condition."""
    op = condition["operator"]
    value = condition.get("value")  # value might be missing for IS NULL

    if op == "IS NULL":
        return variable.is_(None)

    if value is None:
        return variable.is_(None) if op == "==" else variable.is_not(None)
    if isinstance(value, list):
        return variable.in_(value)
    if op == "==":
        return variable == value
    if op == "!=":
        return variable != value
    if op == ">":
        return variable > value
    if op == "<":
        return variable < value
    if op == ">=":
        return variable >= value
    if op == "<=":
        return variable <= value
    raise ValueError(f"Unsupported operator: {op}")


def get_value_column_for_attribute(attr_def: AttrDef) -> Any:
    """Get the correct value column based on the attribute's data type."""
    if attr_def.AttributeDataType == AttributeDataType.Int:
        return AttrVal.ValueInt
    elif attr_def.AttributeDataType == AttributeDataType.Float:
        return AttrVal.ValueFloat
    elif attr_def.AttributeDataType == AttributeDataType.String:
        return AttrVal.ValueText
    elif attr_def.AttributeDataType == AttributeDataType.JSON:
        return AttrVal.ValueJSON
    else:
        # Fallback to text for unknown types
        return AttrVal.ValueText


def convert_search_value_to_attribute_type(value: Any, attr_def: AttrDef) -> Any:
    """Convert search value to match the attribute's data type."""
    if value is None:
        return None

    # Handle list values (for IN operations)
    if isinstance(value, list):
        try:
            if attr_def.AttributeDataType == AttributeDataType.Int:
                return [
                    int(v) if not isinstance(v, bool) else (1 if v else 0)
                    for v in value
                ]
            elif attr_def.AttributeDataType == AttributeDataType.Float:
                return [float(v) for v in value]
            elif attr_def.AttributeDataType == AttributeDataType.String:
                return [str(v) for v in value]
            elif attr_def.AttributeDataType == AttributeDataType.JSON:
                return value  # Keep as-is for JSON
            else:
                return [str(v) for v in value]
        except (ValueError, TypeError):
            # If conversion fails, return as string list for text comparison
            return [str(v) for v in value]

    # Handle single values
    try:
        if attr_def.AttributeDataType == AttributeDataType.Int:
            return int(value) if not isinstance(value, bool) else (1 if value else 0)
        elif attr_def.AttributeDataType == AttributeDataType.Float:
            return float(value)
        elif attr_def.AttributeDataType == AttributeDataType.String:
            return str(value)
        elif attr_def.AttributeDataType == AttributeDataType.JSON:
            # For JSON, we might need special handling
            return value
        else:
            return str(value)
    except (ValueError, TypeError):
        # If conversion fails, return as string for text comparison
        return str(value)


def format_attr_condition_with_definition(
    attr_def: AttrDef, condition: Dict[str, Any]
) -> Any:
    """Format attribute condition using the correct value column based on attribute definition."""
    value_column = get_value_column_for_attribute(attr_def)
    converted_value = convert_search_value_to_attribute_type(
        condition["value"], attr_def
    )

    # Create a new condition with the converted value
    converted_condition = {**condition, "value": converted_value}
    return format_condition(value_column, converted_condition)


def entity_of(attr: Any) -> Any:
    """Return the ORM entity/aliased class that owns the attribute."""
    try:
        # Typical InstrumentedAttribute
        return attr.class_
    except Exception:
        try:
            # Fallback for relationship attributes
            return attr.parent.entity  # type: ignore[attr-defined]
        except Exception:
            try:
                # Last resort
                return sa_inspect(attr).class_  # type: ignore[attr-defined]
            except Exception:
                return None


def partition_conditions_by_entity(
    conditions_mapped: List[Dict[str, Any]],
) -> Dict[Any, List[Dict[str, Any]]]:
    grouped: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for c in conditions_mapped:
        grouped[entity_of(c["variable"])].append(c)
    return grouped


def and_expr(conds: List[Dict[str, Any]]) -> Any:
    if not conds:
        return true()
    return and_(*[format_condition(c["variable"], c) for c in conds])
