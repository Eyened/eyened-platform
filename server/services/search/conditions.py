"""Request DSL -> resolved condition objects.

No DB, no HTTP, no SQLAlchemy expression building: this module only maps UI
labels onto ORM attributes and splits the two condition kinds apart. Expression
construction belongs to ``SearchRepository``, which cannot import from
``server``.
"""
from __future__ import annotations

from typing import Any

from eyened_orm.repositories.search import (
    AttributeConditionSpec,
    ResolvedCondition,
)

from ..exceptions import BadRequestError
from .fields import instance_search_fields_map, study_search_fields_map


class UnknownFieldError(BadRequestError):
    """Raised when a static condition names a field outside the vocabulary.

    Unreachable over HTTP -- ``variable`` is Literal-typed, so Pydantic returns
    422 before a request reaches here. Kept as a guard for non-HTTP callers.

    Subclasses ``BadRequestError`` so an unexpected escape degrades to a 400 via
    the registered ServiceError handler instead of a 500. "Unreachable" plus
    "raises a bare ValueError from the service layer" is how latent 500s are born.
    """


class BadOperatorValueError(BadRequestError):
    """Raised when an operator/value pair has no SQL expression.

    ``format_condition`` reaches ``variable.in_()`` only through its
    ``isinstance(value, list)`` branch, so ``IN`` with a scalar falls through to a
    bare ``ValueError`` -- a 500 for what is plainly a bad request. That helper
    lives in ``orm/`` and cannot import ``BadRequestError``, so the check belongs
    here, at the same boundary that rejects unresolvable attributes.
    """


def _validate_operator_value(operator: str, value: Any) -> None:
    """Reject operator/value pairs the expression builder cannot express."""
    if operator == "IN" and not isinstance(value, list):
        raise BadOperatorValueError(
            f"Operator 'IN' requires a list value, got {type(value).__name__}."
        )


def _resolve(raw: dict[str, Any], fields_map: dict[str, Any]) -> ResolvedCondition:
    label = raw["variable"]
    if label not in fields_map:
        raise UnknownFieldError(f"Invalid variable: {label}")
    _validate_operator_value(raw["operator"], raw.get("value"))
    return ResolvedCondition(
        variable=fields_map[label],
        operator=raw["operator"],
        value=raw.get("value"),
    )


def translate_instance_conditions(
    raw: list[dict[str, Any]],
) -> tuple[list[ResolvedCondition], list[AttributeConditionSpec]]:
    """Split instance conditions into resolved static conditions and attribute specs."""
    static: list[ResolvedCondition] = []
    attrs: list[AttributeConditionSpec] = []
    for cond in raw:
        if cond.get("type") == "attribute":
            attribute = cond.get("variable")
            if not isinstance(attribute, str):
                continue  # preserved verbatim: today's _build_instance_select skips these
            _validate_operator_value(cond["operator"], cond.get("value"))
            attrs.append(
                AttributeConditionSpec(
                    attribute=attribute,
                    operator=cond["operator"],
                    value=cond.get("value"),
                    model=cond.get("model"),
                    feature=cond.get("feature"),
                )
            )
        else:
            static.append(_resolve(cond, instance_search_fields_map))
    return static, attrs


def translate_study_conditions(raw: list[dict[str, Any]]) -> list[ResolvedCondition]:
    """Resolve study conditions against the study vocabulary."""
    return [_resolve(cond, study_search_fields_map) for cond in raw]
