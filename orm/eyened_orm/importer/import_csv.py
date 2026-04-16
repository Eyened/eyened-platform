from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from .importer_dtos import ImportRow


def _none_if_empty(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    return None if v == "" else v


def _parse_bool(value: str | None) -> bool | None:
    v = _none_if_empty(value)
    if v is None:
        return None
    s = v.lower()
    if s in {"1", "true", "t", "yes", "y"}:
        return True
    if s in {"0", "false", "f", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean: {value!r}")


def _parse_int(value: str | None) -> int | None:
    v = _none_if_empty(value)
    return None if v is None else int(v)


def _parse_float(value: str | None) -> float | None:
    v = _none_if_empty(value)
    return None if v is None else float(v)


def _parse_date(value: str | None) -> date | None:
    v = _none_if_empty(value)
    return None if v is None else date.fromisoformat(v)  # YYYY-MM-DD


def _parse_datetime(value: str | None) -> datetime | None:
    v = _none_if_empty(value)
    return None if v is None else datetime.fromisoformat(v)  # ISO 8601


DEFAULT_CSV_CONVERTERS: Mapping[str, Callable[[str | None], Any]] = {
    # IDs / ints
    "project_id": _parse_int,
    "patient_id": _parse_int,
    "study_id": _parse_int,
    "series_id": _parse_int,
    "image_instance_id": _parse_int,
    "storage_backend_id": _parse_int,
    "image_storage_id": _parse_int,
    "series_number": _parse_int,
    "series_anonymous_identity": _parse_int,
    "image_anonymous_identity": _parse_int,
    "height": _parse_int,
    "width": _parse_int,
    "depth": _parse_int,
    "study_round": _parse_int,
    # floats
    "resolution_horizontal": _parse_float,
    "resolution_vertical": _parse_float,
    "resolution_axial": _parse_float,
    "horizontal_field_of_view": _parse_float,
    "threshold": _parse_float,
    # dates / datetimes
    "study_date": _parse_date,
    "acquisition_date_time": _parse_datetime,
    # bools
    "image_storage_is_primary": _parse_bool,
}


def read_import_rows_csv(
    path: str | Path,
    *,
    encoding: str = "utf-8",
    delimiter: str = ",",
    converters: Mapping[str, Callable[[str | None], Any]] | None = None,
    strict_columns: bool = False,
) -> list[ImportRow]:
    """
    Read a CSV into a list of ImportRow objects.

    - Columns should match ImportRow field names (snake_case).
    - Empty cells are treated as None.
    - A small default set of converters is applied for common typed fields (bool/int/float/date/datetime).
    - If strict_columns is True, unknown columns raise a ValueError (instead of being ignored by Pydantic).
    """

    p = Path(path)
    converters = converters or DEFAULT_CSV_CONVERTERS
    allowed = set(ImportRow.model_fields)

    with p.open("r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        rows: list[ImportRow] = []
        for i, raw in enumerate(reader, start=2):  # header is line 1
            data: dict[str, Any] = {}
            for k, v in (raw or {}).items():
                if k is None:
                    continue
                key = k.strip()
                if key == "":
                    continue
                if strict_columns and key not in allowed:
                    raise ValueError(
                        f"Unknown column {key!r} on CSV line {i} (strict_columns=True)"
                    )

                vv = _none_if_empty(v)
                if key in converters:
                    try:
                        data[key] = converters[key](vv)
                    except Exception as e:
                        raise ValueError(
                            f"CSV parse error line {i}, column {key!r}: {e}"
                        ) from e
                else:
                    data[key] = vv

            try:
                rows.append(ImportRow.model_validate(data))
            except Exception as e:
                raise ValueError(f"CSV row validation error on line {i}: {e}") from e

        return rows

