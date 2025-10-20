from __future__ import annotations

from typing import Any, Dict, List, Tuple
from collections import defaultdict

import pandas as pd
from pandas.api import types as pdt

from sqlalchemy.orm import Session
from sqlalchemy import select, inspect as sa_inspect

from eyened_orm import ImageInstance
from eyened_orm.segmentation import Model
from eyened_orm.attributes import Attribute, ImageAttribute, AttributeDataType


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


def df_to_attributes(db: Session, df: pd.DataFrame, *, model_name: str, version: str) -> List[ImageAttribute]:
    """Convert a DataFrame to Attribute and ImageAttribute objects for a model; return the ImageAttribute objects touched."""
    model = db.scalar(select(Model).where(Model.ModelName == model_name, Model.Version == version))
    if not model:
        raise ValueError(f"Model not found: {model_name} / {version}")

    cols = list(df.columns)
    if not cols:
        return []

    # infer types using pandas dtype
    col_types = {col: _infer_column_type(df[col]) for col in cols}

    # upsert Attributes (no flush)
    existing_attrs = {
        a.AttributeName: a
        for a in db.scalars(select(Attribute).where(Attribute.ModelID == model.ModelID)).all()
    }
    attrs_by_name: Dict[str, Attribute] = {}
    for col in cols:
        if col in existing_attrs:
            # validate type reuse
            if existing_attrs[col].AttributeDataType != col_types[col]:
                raise ValueError(
                    f"Attribute type mismatch for {col}: existing={existing_attrs[col].AttributeDataType} new={col_types[col]}"
                )
            attrs_by_name[col] = existing_attrs[col]
        else:
            a = Attribute(AttributeName=col, AttributeDataType=col_types[col], ModelID=model.ModelID)
            db.add(a)
            attrs_by_name[col] = a  # pending

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

    # preload existing ImageAttributes for persistent Attributes only
    persistent_attr_ids = [a.AttributeID for a in attrs_by_name.values() if not sa_inspect(a).pending]
    existing_ia: Dict[Tuple[int, int], ImageAttribute] = {}
    if persistent_attr_ids and image_ids:
        q = select(ImageAttribute).where(
            ImageAttribute.ImageInstanceID.in_(set(image_ids)),
            ImageAttribute.AttributeID.in_(set(persistent_attr_ids)),
        )
        for ia in db.scalars(q).all():
            existing_ia[(ia.ImageInstanceID, ia.AttributeID)] = ia

    touched: List[ImageAttribute] = []
    for idx, image_id in zip(idx_values, image_ids):
        for col, attr in attrs_by_name.items():
            if col not in df.columns:
                continue
            raw_val = df.at[idx, col]
            if _is_nullish(raw_val):
                continue

            dtype = attr.AttributeDataType
            if sa_inspect(attr).pending:
                ia = ImageAttribute(ImageInstanceID=image_id, Attribute=attr)
            else:
                key = (image_id, attr.AttributeID)
                ia = existing_ia.get(key)
                if ia is None:
                    ia = ImageAttribute(ImageInstanceID=image_id, AttributeID=attr.AttributeID)

            # assign per dtype
            if dtype == AttributeDataType.Int:
                ia.ValueInt = int(raw_val) if not isinstance(raw_val, bool) else (1 if raw_val else 0)
                ia.ValueFloat = None
                ia.ValueText = None
                ia.ValueJSON = None
            elif dtype == AttributeDataType.Float:
                ia.ValueFloat = float(raw_val)
                ia.ValueInt = None
                ia.ValueText = None
                ia.ValueJSON = None
            else:
                ia.ValueText = str(raw_val)
                ia.ValueInt = None
                ia.ValueFloat = None
                ia.ValueJSON = None

            if sa_inspect(ia).transient:
                db.add(ia)
            touched.append(ia)

    return touched


def print_import_summary(attributes: List[Attribute], image_attributes: List[ImageAttribute]) -> None:
    """Print a summary grouped by Attribute: new vs existing, and per-attribute new vs updated ImageAttributes."""
    # group by Attribute
    groups: Dict[Attribute, List[ImageAttribute]] = defaultdict(list)
    for ia in image_attributes:
        if ia.Attribute is None:
            continue
        groups[ia.Attribute].append(ia)

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
            new_ias = sum(1 for ia in items if sa_inspect(ia).pending or sa_inspect(ia).transient)
            print(f"  - {attr.AttributeName}: {new_ias} inserted")

    # print existing attributes
    if existing_attrs:
        print("Existing Attributes:")
        for attr, items in sorted(existing_attrs, key=lambda x: x[0].AttributeName):
            new_ias = sum(1 for ia in items if sa_inspect(ia).pending or sa_inspect(ia).transient)
            
            def is_updated(ia: ImageAttribute) -> bool:
                st = sa_inspect(ia)
                if st.transient or st.pending:
                    return False
                keys = ("ValueInt", "ValueFloat", "ValueText", "ValueJSON")
                return any(st.attrs[k].history.has_changes() for k in keys if hasattr(ia, k))
            
            upd_ias = sum(1 for ia in items if is_updated(ia))
            print(f"  - {attr.AttributeName}: {new_ias} new, {upd_ias} updated")


