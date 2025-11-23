from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

import pandas as pd
from pandas.api import types as pdt
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm.attributes import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModelOutput,
    AttributeValue,
)
from eyened_orm.segmentation import Model


def _is_nullish(value: Any) -> bool:
    """Return True for None/NaN/empty-string and explicit 'null'/'NULL'."""
    if value is None:
        return True
    if isinstance(value, str) and value in ("", "null", "NULL"):
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def _infer_column_type(col: pd.Series) -> AttributeDataType:
    """Infer AttributeDataType from pandas dtype. Booleans are treated as Int; JSON is not supported."""
    if pdt.is_bool_dtype(col) or pdt.is_integer_dtype(col):
        return AttributeDataType.Int
    if pdt.is_float_dtype(col):
        return AttributeDataType.Float
    return AttributeDataType.String


def df_to_attributes(
    db: Session, df: pd.DataFrame, *, model_name: str, version: str
) -> List[AttributeValue]:
    """Convert a DataFrame to AttributeDefinition and AttributeValue objects for a model; return the AttributeValue objects touched."""
    model = db.scalar(
        select(Model).where(Model.ModelName == model_name, Model.Version == version)
    )
    if not model:
        raise ValueError(f"Model not found: {model_name} / {version}")

    cols = list(df.columns)
    if not cols:
        return []

    # infer types using pandas dtype
    col_types = {col: _infer_column_type(df[col]) for col in cols}

    # upsert AttributeDefinitions (globally, not per-model)
    existing_attrs = {
        a.AttributeName: a for a in db.scalars(select(AttributeDefinition)).all()
    }
    attrs_by_name: Dict[str, AttributeDefinition] = {}
    for col in cols:
        if col in existing_attrs:
            # validate type consistency
            if existing_attrs[col].AttributeDataType != col_types[col]:
                raise ValueError(
                    f"Attribute type mismatch for {col}: existing={existing_attrs[col].AttributeDataType} new={col_types[col]}"
                )
            attrs_by_name[col] = existing_attrs[col]
        else:
            a = AttributeDefinition(AttributeName=col, AttributeDataType=col_types[col])
            db.add(a)
            attrs_by_name[col] = a  # pending

    # Ensure AttributesModelOutput entries exist for this model
    db.flush()  # Get AttributeIDs for pending attributes
    for attr in attrs_by_name.values():
        existing_link = db.scalar(
            select(AttributesModelOutput).where(
                AttributesModelOutput.ModelID == model.ModelID,
                AttributesModelOutput.AttributeID == attr.AttributeID,
            )
        )
        if not existing_link:
            db.add(
                AttributesModelOutput(
                    ModelID=model.ModelID, AttributeID=attr.AttributeID
                )
            )

    # load images
    image_ids: List[int] = []
    idx_values: List[Any] = []
    for idx in df.index:
        try:
            iid = int(idx)
        except Exception:
            continue
        image_ids.append(iid)
        idx_values.append(idx)

    # preload existing AttributeValues for persistent AttributeDefinitions only
    persistent_attr_ids = [
        a.AttributeID for a in attrs_by_name.values() if not sa_inspect(a).pending
    ]
    existing_av: Dict[
        Tuple[int, int, int], AttributeValue
    ] = {}  # (ImageInstanceID, AttributeID, ModelID)
    if persistent_attr_ids and image_ids:
        q = select(AttributeValue).where(
            AttributeValue.ImageInstanceID.in_(set(image_ids)),
            AttributeValue.AttributeID.in_(set(persistent_attr_ids)),
            AttributeValue.ModelID == model.ModelID,
        )
        for av in db.scalars(q).all():
            existing_av[(av.ImageInstanceID, av.AttributeID, av.ModelID)] = av

    touched: List[AttributeValue] = []
    for idx, image_id in zip(idx_values, image_ids):
        for col, attr in attrs_by_name.items():
            if col not in df.columns:
                continue
            raw_val = df.at[idx, col]
            if _is_nullish(raw_val):
                continue

            dtype = attr.AttributeDataType
            if sa_inspect(attr).pending:
                av = AttributeValue(
                    ImageInstanceID=image_id,
                    AttributeID=attr.AttributeID,
                    ModelID=model.ModelID,
                )
            else:
                key = (image_id, attr.AttributeID, model.ModelID)
                av = existing_av.get(key)
                if av is None:
                    av = AttributeValue(
                        ImageInstanceID=image_id,
                        AttributeID=attr.AttributeID,
                        ModelID=model.ModelID,
                    )

            # assign per dtype
            if dtype == AttributeDataType.Int:
                av.ValueInt = (
                    int(raw_val)
                    if not isinstance(raw_val, bool)
                    else (1 if raw_val else 0)
                )
                av.ValueFloat = None
                av.ValueText = None
                av.ValueJSON = None
            elif dtype == AttributeDataType.Float:
                av.ValueFloat = float(raw_val)
                av.ValueInt = None
                av.ValueText = None
                av.ValueJSON = None
            else:
                av.ValueText = str(raw_val)
                av.ValueInt = None
                av.ValueFloat = None
                av.ValueJSON = None

            if sa_inspect(av).transient:
                db.add(av)
            touched.append(av)

    return touched


def print_import_summary(
    attributes: List[AttributeDefinition], attribute_values: List[AttributeValue]
) -> None:
    """Print a summary grouped by AttributeDefinition: new vs existing, and per-attribute new vs updated AttributeValues."""
    # group by AttributeDefinition
    groups: Dict[AttributeDefinition, List[AttributeValue]] = defaultdict(list)
    for av in attribute_values:
        attr_def = getattr(av, "AttributeDefinition", None)
        if attr_def is None:
            continue
        groups[attr_def].append(av)

    # partition attributes by new vs existing
    new_attrs = []
    existing_attrs = []
    for attr, items in groups.items():
        if sa_inspect(attr).pending or sa_inspect(attr).transient:
            new_attrs.append((attr, items))
        else:
            existing_attrs.append((attr, items))

    # print new attributes
    if new_attrs:
        print("New Attributes:")
        for attr, items in sorted(new_attrs, key=lambda x: x[0].AttributeName):
            new_avs = sum(
                1 for av in items if sa_inspect(av).pending or sa_inspect(av).transient
            )
            print(f"  - {attr.AttributeName}: {new_avs} inserted")

    # print existing attributes
    if existing_attrs:
        print("Existing Attributes:")
        for attr, items in sorted(existing_attrs, key=lambda x: x[0].AttributeName):
            new_avs = sum(
                1 for av in items if sa_inspect(av).pending or sa_inspect(av).transient
            )

            def is_updated(av: AttributeValue) -> bool:
                st = sa_inspect(av)
                if st.transient or st.pending:
                    return False
                keys = ("ValueInt", "ValueFloat", "ValueText", "ValueJSON")
                return any(
                    st.attrs[k].history.has_changes() for k in keys if hasattr(av, k)
                )

            upd_avs = sum(1 for av in items if is_updated(av))
            print(f"  - {attr.AttributeName}: {new_avs} new, {upd_avs} updated")
