from __future__ import annotations

import csv
import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

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


def _parse_json(value: str | None) -> Any | None:
    v = _none_if_empty(value)
    if v is None:
        return None
    return json.loads(v)


def _parse_bytes_hex(value: str | None) -> bytes | None:
    v = _none_if_empty(value)
    if v is None:
        return None
    return bytes.fromhex(v)


DEFAULT_CSV_CONVERTERS: Mapping[str, Callable[[str | None], Any]] = {
    # IDs / ints
    "project_id": _parse_int,
    "contact_id": _parse_int,
    "patient_id": _parse_int,
    "study_id": _parse_int,
    "series_id": _parse_int,
    "image_instance_id": _parse_int,
    "scan_id": _parse_int,
    "modality_id": _parse_int,
    "storage_backend_id": _parse_int,
    "image_storage_id": _parse_int,
    "source_info_id": _parse_int,
    "anatomic_region": _parse_int,
    "samples_per_pixel": _parse_int,
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
    "slice_thickness": _parse_float,
    "cf_quality": _parse_float,
    "threshold": _parse_float,
    # dates / datetimes
    "study_date": _parse_date,
    "acquisition_date_time": _parse_datetime,
    "date_inserted": _parse_datetime,
    "date_modified": _parse_datetime,
    "date_preprocessed": _parse_datetime,
    # JSON (ImageInstance CF* columns)
    "cf_roi": _parse_json,
    "cf_keypoints": _parse_json,
    # bools
    "image_storage_is_primary": _parse_bool,
    "inactive": _parse_bool,
    # hashes
    "image_storage_hash": _parse_bytes_hex,
}


def _csv_cell(value: Any) -> str:
    """Serialize an ImportRow field value for CSV (empty string for None)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, datetime):
        return value.isoformat(sep="T", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    return str(value)


def _columns_for_rows(
    rows: Sequence[ImportRow],
    *,
    columns: Sequence[str] | None,
    include_empty: bool,
) -> list[str]:
    field_order = list(ImportRow.model_fields)
    allowed = set(field_order)
    if columns is not None:
        unknown = [c for c in columns if c not in allowed]
        if unknown:
            raise ValueError(f"Unknown ImportRow column(s): {unknown!r}")
        return list(columns)

    if include_empty:
        return field_order

    used: set[str] = set()
    for row in rows:
        dump = row.model_dump(exclude_none=True)
        used.update(dump.keys())
    return [c for c in field_order if c in used]


def write_import_rows_csv(
    rows: Sequence[ImportRow],
    path: str | Path,
    *,
    encoding: str = "utf-8",
    delimiter: str = ",",
    columns: Sequence[str] | None = None,
    include_empty: bool = False,
) -> Path:
    """
    Write ``ImportRow`` instances to a CSV readable by ``read_import_rows_csv``.

    Useful after ``prepare_rows`` / ``build_image_import_rows`` so inferred DICOM /
    default metadata can be inspected (and optionally edited) before
    ``plan_import``. Prefer that split workflow over ``plan_image_import`` when
    you need the CSV: ``plan_image_import`` does not return the prepared rows.

    - Column names are ``ImportRow`` field names (snake_case).
    - ``None`` becomes an empty cell.
    - Enums, dates/datetimes, bools, and ``bytes`` (hex) use formats accepted by
      ``read_import_rows_csv``.
    - By default only columns with at least one non-``None`` value are written.
      Pass ``include_empty=True`` for every ``ImportRow`` field, or ``columns=...``
      for an explicit header.
    """
    p = Path(path)
    header = _columns_for_rows(rows, columns=columns, include_empty=include_empty)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=header,
            delimiter=delimiter,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            dump = row.model_dump()
            writer.writerow({k: _csv_cell(dump.get(k)) for k in header})
    return p


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
    - Empty cells are omitted (field unset), so DICOM/defaults preparation may fill them.
      To leave a field blank on purpose, construct ``ImportRow`` in Python with an
      explicit ``None`` (see row preparation pinning).
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
                        parsed = converters[key](vv)
                    except Exception as e:
                        raise ValueError(
                            f"CSV parse error line {i}, column {key!r}: {e}"
                        ) from e
                    if parsed is not None:
                        data[key] = parsed
                elif vv is not None:
                    data[key] = vv

            try:
                rows.append(ImportRow.model_validate(data))
            except Exception as e:
                raise ValueError(f"CSV row validation error on line {i}: {e}") from e

        return rows
