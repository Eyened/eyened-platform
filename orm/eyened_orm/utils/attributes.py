from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from pandas.api import types as pdt
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from eyened_orm.attributes import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModel,
    AttributeValue,
)


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


def ensure_model_output_attribute(
    db: Session, model: AttributesModel, attr: AttributeDefinition
) -> None:
    """
    Idempotently ensure `attr` is declared as an output of `model`.

    Uses the ORM relationship (`model.OutputAttributes`) for brevity.
    """
    db.flush()  # ensure PKs are available
    if attr.AttributeID is None:
        raise ValueError(
            "AttributeDefinition must have AttributeID (flush before linking)"
        )
    # Avoid duplicates even if `attr` is a different instance with the same PK.
    if any(a.AttributeID == attr.AttributeID for a in model.OutputAttributes):
        return
    model.OutputAttributes.append(attr)
    db.flush()


def _build_attribute_update_values(
    dtype: AttributeDataType, raw_val: Any
) -> Dict[str, Any]:
    """Build update_values dict for AttributeValue based on dtype."""
    if dtype == AttributeDataType.Int:
        return {"ValueInt": int(raw_val)}
    elif dtype == AttributeDataType.Float:
        return {"ValueFloat": float(raw_val)}
    elif dtype == AttributeDataType.String:
        return {"ValueText": str(raw_val)}
    else:
        raise ValueError(
            f"Unsupported AttributeDataType for df_to_attributes(): {dtype}"
        )


def _safe_int(value: Any) -> Optional[int]:
    """Best-effort int conversion; returns None if conversion fails."""
    try:
        return int(value)
    except Exception:
        return None


def df_to_attributes(
    session: Session, df: pd.DataFrame, *, model_name: str, version: str
) -> List[AttributeValue]:
    """Convert a DataFrame to AttributeDefinition and AttributeValue objects for a model; return the AttributeValue objects touched."""
    model = AttributesModel.by_column(session, ModelName=model_name, Version=version)
    if not model:
        raise ValueError(f"Model not found: {model_name} / {version}")

    cols = list(df.columns)
    if not cols:
        return []

    # infer types using pandas dtype
    col_types = {name: _infer_column_type(df[name]) for name in cols}

    # upsert AttributeDefinitions (globally, not per-model)
    attrs_by_name: Dict[str, AttributeDefinition] = {
        name: AttributeDefinition.get_or_create(
            session, match_by={"AttributeName": name, "AttributeDataType": dtype}
        )
        for name, dtype in col_types.items()
    }

    # Ensure model declares these outputs (idempotent)
    for attr in attrs_by_name.values():
        ensure_model_output_attribute(session, model, attr)

    # load images
    # Map DataFrame index values to ImageInstanceIDs (skip non-int-like indices).
    idx_to_image_id: Dict[Any, int] = {
        idx: iid for idx in df.index if (iid := _safe_int(idx)) is not None
    }
    image_ids = set(idx_to_image_id.values())

    # Prefetch existing AttributeValues
    attr_ids = {
        a.AttributeID for a in attrs_by_name.values() if a.AttributeID is not None
    }
    existing_av: Dict[Tuple[int, int, int], AttributeValue] = {}
    if attr_ids and image_ids:
        existing_av = {
            (av.ImageInstanceID, av.AttributeID, av.ModelID): av
            for av in AttributeValue.where(
                session,
                (AttributeValue.ImageInstanceID.in_(image_ids))
                & (AttributeValue.AttributeID.in_(attr_ids))
                & (AttributeValue.ModelID == model.ModelID),
            )
        }

    touched: List[AttributeValue] = []
    for idx, image_id in idx_to_image_id.items():
        for name, attr in attrs_by_name.items():
            raw_val = df.at[idx, name]
            if _is_nullish(raw_val):
                continue

            update_values = _build_attribute_update_values(
                attr.AttributeDataType, raw_val
            )
            key = (image_id, attr.AttributeID, model.ModelID)

            # Use prefetched instance if available
            av = existing_av.get(key)
            if av:
                # Update prefetched instance directly (no DB query needed)
                for k, v in update_values.items():
                    setattr(av, k, v)
            else:
                av = AttributeValue.upsert(
                    session,
                    match_by={
                        "ImageInstanceID": image_id,
                        "AttributeID": attr.AttributeID,
                        "ModelID": model.ModelID,
                    },
                    update_values=update_values,
                )
            touched.append(av)

    return touched


def print_import_summary(
    attributes: List[AttributeDefinition], attribute_values: List[AttributeValue]
) -> None:
    """Print a summary grouped by AttributeDefinition: new vs existing, and per-attribute new vs updated AttributeValues."""
    # group by AttributeDefinition
    groups: Dict[AttributeDefinition, List[AttributeValue]] = defaultdict(list)
    for av in attribute_values:
        # AttributeDefinition is a required relationship (AttributeID is NOT NULL)
        # Skip if relationship not accessible (e.g., transient object or session closed)
        try:
            attr_def = av.AttributeDefinition
        except (AttributeError, RuntimeError):
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
