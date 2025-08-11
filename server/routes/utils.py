import os
from typing import Optional, get_origin

from pydantic import create_model

def collect_rows(rows):
    def to_dict(row):
        return {
            k: v for k, v in row.to_dict().items() if k not in ("ValueBlob", "FormData")
        }

    return [
        to_dict(row)
        for row in rows
        # the tuples (None, None) are returned by the tags linking tables
        if (row is not None) and (row != (None, None))
    ]


def model_omit(model, omit_fields):
    """
    Returns a new Pydantic model class with the specified fields omitted.
    :param model: The original Pydantic model class.
    :param omit_fields: A set or list of field names to omit.
    """
    fields = {
        name: (field.outer_type_, field.default)
        for name, field in model.__fields__.items()
        if name not in omit_fields
    }
    return create_model(f"{model.__name__}Omit", **fields)


def model_pick(model, pick_fields):
    """
    Returns a new Pydantic model class with only the specified fields included.
    :param model: The original Pydantic model class.
    :param pick_fields: A set or list of field names to include.
    """
    fields = {
        name: (field.outer_type_, field.default)
        for name, field in model.__fields__.items()
        if name in pick_fields
    }
    return create_model(f"{model.__name__}Pick", **fields)


def model_partial(model):
    """
    Returns a new Pydantic model class with all fields made Optional and defaulting to None.
    :param model: The original Pydantic model class.
    """
    fields = {}
    for name, field in model.__fields__.items():
        # If already Optional, keep as is; else wrap in Optional
        field_type = field.outer_type_
        if get_origin(field_type) is Optional:
            optional_type = field_type
        else:
            optional_type = Optional[field_type]
        fields[name] = (optional_type, None)
    return create_model(f"{model.__name__}Partial", **fields)