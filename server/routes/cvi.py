from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import get_db
from .auth import CurrentUser, get_current_user, is_admin_user

router = APIRouter(prefix="/cvi", tags=["cvi"])

TABLE_NAME = "CVIData"
CHANGES_TABLE_NAME = "CVIChanges"
CREATOR_TABLE = "Creator"
PDF_ROOT = Path("/mnt/qnap-rc-02/Eyened-temp-for-test/pdfs")

REQUESTED_FIELDS = [
    "added_by",
    "data_added",
    "form_ID",
    "folder_number",
    "nhs_number",
    "patient_name",
    "visual_status",
    "patient_postcode",
    "dob",
    "gender",
    "form_version",
    "potential_duplicate_warning",
    "patient_town",
    "patient_date",
    "signatory_is",
    "signatory_check",
    "registration_date",
    "hospital_name",
    "hospital_name_other",
    "social_service_department",
    "social_service_department_extracted",
    "red1",
    "red2",
    "led1",
    "led2",
    "main_diagnosis",
    "main_cause_from",
    "q1",
    "q2",
    "q3",
    "q4",
    "q5",
    "q6",
    "q7",
    "patient_is",
    "ethnicity",
    "data_access_group",
    "recieved_by",
    "status",
    "pdf_file",
]


class CVIUpdatePayload(BaseModel):
    values: dict[str, Any]


class CVIRecordResponse(BaseModel):
    id: Any
    id_column: str
    record: dict[str, Any]
    added_by_display_name: Optional[str] = None
    pdf_url: Optional[str] = None


class CVINextResponse(BaseModel):
    current: Optional[CVIRecordResponse] = None
    next: Optional[CVIRecordResponse] = None


class CVIPreviousResponse(BaseModel):
    current: Optional[CVIRecordResponse] = None
    previous: Optional[CVIRecordResponse] = None


class CVIPdfIndexItem(BaseModel):
    id: Any
    form_ID: Optional[Any] = None
    pdf_file: str
    pdf_url: str
    status: Optional[str] = None



def _q(identifier: str) -> str:
    return f"`{identifier.replace('`', '``')}`"



def _inspect_table(db: Session) -> tuple[str, list[str]]:
    engine = db.get_bind()
    if engine is None:
        raise HTTPException(status_code=500, detail="Database engine not available")

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if TABLE_NAME not in tables:
        raise HTTPException(status_code=404, detail="CVIData table not found")

    columns = [c["name"] for c in inspector.get_columns(TABLE_NAME)]
    pk = inspector.get_pk_constraint(TABLE_NAME).get("constrained_columns") or []

    if pk:
        pk_col = pk[0]
    elif "id" in columns:
        pk_col = "id"
    else:
        pk_col = columns[0]

    return pk_col, columns


def _inspect_changes_table(db: Session) -> tuple[str, list[str]]:
    engine = db.get_bind()
    if engine is None:
        raise HTTPException(status_code=500, detail="Database engine not available")

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if CHANGES_TABLE_NAME not in tables:
        raise HTTPException(status_code=404, detail="CVIChanges table not found")

    columns = [c["name"] for c in inspector.get_columns(CHANGES_TABLE_NAME)]
    pk = inspector.get_pk_constraint(CHANGES_TABLE_NAME).get("constrained_columns") or []

    if pk:
        pk_col = pk[0]
    elif "id" in columns:
        pk_col = "id"
    else:
        pk_col = columns[0]

    return pk_col, columns


def _record_cvi_changes(
    db: Session,
    record_id: Any,
    changed_keys: list[str],
) -> None:
    changes_pk_col, changes_columns = _inspect_changes_table(db)

    increment_columns = [k for k in changed_keys if k in changes_columns and k != changes_pk_col]
    if "changes" in changes_columns and "changes" != changes_pk_col:
        increment_columns.append("changes")

    if not increment_columns:
        return

    db.execute(
        text(
            f"INSERT INTO {_q(CHANGES_TABLE_NAME)} ({_q(changes_pk_col)}) "
            f"VALUES (:record_id) "
            f"ON DUPLICATE KEY UPDATE {_q(changes_pk_col)} = {_q(changes_pk_col)}"
        ),
        {"record_id": record_id},
    )

    set_parts = [f"{_q(col)} = COALESCE({_q(col)}, 0) + 1" for col in increment_columns]
    db.execute(
        text(
            f"UPDATE {_q(CHANGES_TABLE_NAME)} SET {', '.join(set_parts)} "
            f"WHERE {_q(changes_pk_col)} = :record_id"
        ),
        {"record_id": record_id},
    )



def _serialize_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value



def _resolve_creator_name(db: Session, creator_id: Any) -> Optional[str]:
    if creator_id in (None, "", 0, "0"):
        return None
    row = db.execute(
        text(f"SELECT CreatorName FROM {_q(CREATOR_TABLE)} WHERE CreatorID = :creator_id LIMIT 1"),
        {"creator_id": creator_id},
    ).mappings().first()
    if row is None:
        return None
    return row.get("CreatorName")



def _pdf_url_for_record(record_id: Any, record: dict[str, Any]) -> Optional[str]:
    if not record.get("pdf_file"):
        return None
    return f"/api/cvi/pdf/{record_id}"


def _resolve_pdf_candidate(pdf_file: Any) -> Path:
    raw = str(pdf_file).strip().strip('"').strip("'").replace("\\", "/")
    if not raw:
        raise HTTPException(status_code=404, detail="No PDF linked to this row")

    # Common exports may store `pdfs/<name>.pdf`; keep the path rooted once.
    if raw.startswith("pdfs/"):
        raw = raw[len("pdfs/"):]

    if raw.startswith("/"):
        candidate = Path(raw)
    else:
        candidate = PDF_ROOT / raw

    return candidate.resolve()



def _to_response(
    db: Session,
    current_user: CurrentUser,
    id_column: str,
    record_id: Any,
    record: dict[str, Any],
) -> CVIRecordResponse:
    creator_name = _resolve_creator_name(db, record.get("added_by"))
    added_by_display_name = creator_name or current_user.username
    serialized = {k: _serialize_value(v) for k, v in record.items()}
    return CVIRecordResponse(
        id=record_id,
        id_column=id_column,
        record=serialized,
        added_by_display_name=added_by_display_name,
        pdf_url=_pdf_url_for_record(record_id, record),
    )



def _select_fields(columns: list[str]) -> list[str]:
    fields = [field for field in REQUESTED_FIELDS if field in columns]
    if "pdf_file" not in fields and "pdf_file" in columns:
        fields.append("pdf_file")
    if "users_ID" in columns and "users_ID" not in fields:
        fields.append("users_ID")
    if "SubTaskID" in columns and "SubTaskID" not in fields:
        fields.append("SubTaskID")
    if "changes" in columns and "changes" not in fields:
        fields.append("changes")
    return fields


def _assigned_filter_sql(current_user: CurrentUser, db: Session, columns: list[str]) -> tuple[str, dict[str, Any]]:
    if is_admin_user(current_user, db):
        return "", {}

    subtask_column = "SubTaskID" if "SubTaskID" in columns else None
    if subtask_column is None:
        for candidate in ["subtask_id", "sub_task_id"]:
            if candidate in columns:
                subtask_column = candidate
                break

    if subtask_column is not None:
        return (
            f" WHERE {_q(subtask_column)} IN ("
            f"SELECT {_q('SubTaskID')} FROM {_q('SubTask')} "
            f"WHERE {_q('CreatorID')} = :assigned_user_id"
            f")",
            {"assigned_user_id": current_user.id},
        )

    if "users_ID" in columns:
        return f" WHERE {_q('users_ID')} = :assigned_user_id", {"assigned_user_id": current_user.id}

    return "", {}



def _fetch_record_by_id(db: Session, id_column: str, fields: list[str], record_id: Any) -> Optional[dict[str, Any]]:
    selected = ", ".join([_q(id_column)] + [_q(field) for field in fields if field != id_column])
    query = text(
        f"SELECT {selected} FROM {_q(TABLE_NAME)} "
        f"WHERE {_q(id_column)} = :record_id LIMIT 1"
    )
    row = db.execute(query, {"record_id": record_id}).mappings().first()
    if row is None:
        return None
    return dict(row)


def _fetch_record_by_id_scoped(
    db: Session,
    id_column: str,
    fields: list[str],
    record_id: Any,
    current_user: CurrentUser,
    columns: list[str],
) -> Optional[dict[str, Any]]:
    selected = ", ".join([_q(id_column)] + [_q(field) for field in fields if field != id_column])
    where_sql, params = _assigned_filter_sql(current_user, db, columns)
    scoped_where = f"{where_sql} AND {_q(id_column)} = :record_id" if where_sql else f"WHERE {_q(id_column)} = :record_id"
    row = db.execute(
        text(f"SELECT {selected} FROM {_q(TABLE_NAME)} {scoped_where} LIMIT 1"),
        {**params, "record_id": record_id},
    ).mappings().first()
    if row is None:
        return None
    return dict(row)


@router.get("/record/first", response_model=CVIRecordResponse)
async def get_first_cvi_record(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    id_column, columns = _inspect_table(db)
    fields = _select_fields(columns)
    selected = ", ".join([_q(id_column)] + [_q(field) for field in fields if field != id_column])
    where_sql, params = _assigned_filter_sql(current_user, db, columns)

    row = db.execute(
        text(f"SELECT {selected} FROM {_q(TABLE_NAME)}{where_sql} ORDER BY {_q(id_column)} ASC LIMIT 1"),
        params,
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="No CVIData rows found")

    record = dict(row)
    return _to_response(db, current_user, id_column, record[id_column], record)


@router.get("/record/by-form-id/{form_id}", response_model=CVIRecordResponse)
async def get_cvi_record_by_form_id(
    form_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    id_column, columns = _inspect_table(db)
    if "form_ID" not in columns:
        raise HTTPException(status_code=400, detail="form_ID column not found in CVIData")

    fields = _select_fields(columns)
    selected = ", ".join([_q(id_column)] + [_q(field) for field in fields if field != id_column])
    where_sql, params = _assigned_filter_sql(current_user, db, columns)
    scope_and = f"{where_sql} AND" if where_sql else " WHERE"

    row = db.execute(
        text(
            f"SELECT {selected} FROM {_q(TABLE_NAME)} "
            f"{scope_and} {_q('form_ID')} = :form_id "
            f"ORDER BY {_q(id_column)} ASC LIMIT 1"
        ),
        {**params, "form_id": form_id},
    ).mappings().first()

    if row is None:
        raise HTTPException(status_code=404, detail="CVIData row not found for this form_ID")

    record = dict(row)
    return _to_response(db, current_user, id_column, record[id_column], record)


@router.get("/records/pdf-index", response_model=list[CVIPdfIndexItem])
async def get_cvi_pdf_index(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    id_column, columns = _inspect_table(db)
    if "pdf_file" not in columns:
        return []

    selected_fields = [_q(id_column), _q("pdf_file")]
    if "form_ID" in columns:
        selected_fields.append(_q("form_ID"))
    if "status" in columns:
        selected_fields.append(_q("status"))

    where_sql, params = _assigned_filter_sql(current_user, db, columns)
    scope_and = f"{where_sql} AND" if where_sql else " WHERE"
    rows = db.execute(
        text(
            f"SELECT {', '.join(selected_fields)} FROM {_q(TABLE_NAME)} "
            f"{scope_and} {_q('pdf_file')} IS NOT NULL AND TRIM({_q('pdf_file')}) <> '' "
            f"ORDER BY {_q(id_column)} ASC LIMIT :limit"
        ),
        {**params, "limit": max(1, min(limit, 5000))},
    ).mappings().all()

    items: list[CVIPdfIndexItem] = []
    for row in rows:
        record = dict(row)
        record_id = record[id_column]
        pdf_file = str(record.get("pdf_file") or "").strip()
        if not pdf_file:
            continue
        items.append(
            CVIPdfIndexItem(
                id=record_id,
                form_ID=record.get("form_ID"),
                pdf_file=pdf_file,
                pdf_url=f"/api/cvi/pdf/{record_id}",
                status=record.get("status"),
            )
        )

    return items


@router.get("/record/{record_id}", response_model=CVIRecordResponse)
async def get_cvi_record(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    id_column, columns = _inspect_table(db)
    fields = _select_fields(columns)
    record = _fetch_record_by_id_scoped(db, id_column, fields, record_id, current_user, columns)
    if record is None:
        raise HTTPException(status_code=404, detail="CVIData row not found")
    return _to_response(db, current_user, id_column, record[id_column], record)


@router.get("/record/{record_id}/next", response_model=CVINextResponse)
async def get_next_cvi_record(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    id_column, columns = _inspect_table(db)
    fields = _select_fields(columns)

    current_record = _fetch_record_by_id_scoped(db, id_column, fields, record_id, current_user, columns)
    if current_record is None:
        raise HTTPException(status_code=404, detail="Current CVIData row not found")

    selected = ", ".join([_q(id_column)] + [_q(field) for field in fields if field != id_column])
    where_sql, params = _assigned_filter_sql(current_user, db, columns)
    scope_and = f"{where_sql} AND" if where_sql else " WHERE"
    next_row = db.execute(
        text(
            f"SELECT {selected} FROM {_q(TABLE_NAME)} "
            f"{scope_and} {_q(id_column)} > :record_id "
            f"ORDER BY {_q(id_column)} ASC LIMIT 1"
        ),
        {**params, "record_id": record_id},
    ).mappings().first()

    next_record = dict(next_row) if next_row is not None else None

    return CVINextResponse(
        current=_to_response(db, current_user, id_column, current_record[id_column], current_record),
        next=(
            _to_response(db, current_user, id_column, next_record[id_column], next_record)
            if next_record is not None
            else None
        ),
    )


@router.get("/record/{record_id}/previous", response_model=CVIPreviousResponse)
async def get_previous_cvi_record(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    id_column, columns = _inspect_table(db)
    fields = _select_fields(columns)

    current_record = _fetch_record_by_id_scoped(db, id_column, fields, record_id, current_user, columns)
    if current_record is None:
        raise HTTPException(status_code=404, detail="Current CVIData row not found")

    selected = ", ".join([_q(id_column)] + [_q(field) for field in fields if field != id_column])
    where_sql, params = _assigned_filter_sql(current_user, db, columns)
    scope_and = f"{where_sql} AND" if where_sql else " WHERE"
    previous_row = db.execute(
        text(
            f"SELECT {selected} FROM {_q(TABLE_NAME)} "
            f"{scope_and} {_q(id_column)} < :record_id "
            f"ORDER BY {_q(id_column)} DESC LIMIT 1"
        ),
        {**params, "record_id": record_id},
    ).mappings().first()

    previous_record = dict(previous_row) if previous_row is not None else None

    return CVIPreviousResponse(
        current=_to_response(db, current_user, id_column, current_record[id_column], current_record),
        previous=(
            _to_response(db, current_user, id_column, previous_record[id_column], previous_record)
            if previous_record is not None
            else None
        ),
    )


@router.patch("/record/{record_id}", response_model=CVIRecordResponse)
async def update_cvi_record(
    record_id: str,
    payload: CVIUpdatePayload,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    id_column, columns = _inspect_table(db)
    allowed_columns = set(columns) - {id_column}
    fields = _select_fields(columns)

    current_record = _fetch_record_by_id_scoped(db, id_column, fields, record_id, current_user, columns)
    if current_record is None:
        raise HTTPException(status_code=404, detail="CVIData row not found")

    values = payload.values or {}
    if not values:
        raise HTTPException(status_code=400, detail="No values provided")

    invalid = [key for key in values.keys() if key not in allowed_columns]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown columns: {', '.join(invalid)}")

    changed_values: dict[str, Any] = {}
    for key, new_value in values.items():
        current_value = current_record.get(key)
        if (current_value is None and new_value is None) or current_value == new_value:
            continue
        changed_values[key] = new_value

    if not changed_values:
        return _to_response(db, current_user, id_column, current_record[id_column], current_record)

    changed_keys = list(changed_values.keys())
    set_parts = [f"{_q(key)} = :{key}" for key in changed_keys]
    if "changes" in columns and "changes" not in changed_values:
        set_parts.append(f"{_q('changes')} = COALESCE({_q('changes')}, 0) + 1")

    params = {**changed_values, "record_id": record_id}

    try:
        db.execute(
            text(
                f"UPDATE {_q(TABLE_NAME)} SET {', '.join(set_parts)} "
                f"WHERE {_q(id_column)} = :record_id"
            ),
            params,
        )

        _record_cvi_changes(db, record_id, changed_keys)

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update CVIData row: {exc}") from exc

    updated = _fetch_record_by_id_scoped(db, id_column, fields, record_id, current_user, columns)
    if updated is None:
        raise HTTPException(status_code=404, detail="CVIData row not found after update")

    return _to_response(db, current_user, id_column, updated[id_column], updated)


@router.get("/pdf/{record_id}")
async def get_cvi_pdf(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    id_column, columns = _inspect_table(db)
    if "pdf_file" not in columns:
        raise HTTPException(status_code=404, detail="pdf_file column not found in CVIData")

    where_sql, params = _assigned_filter_sql(current_user, db, columns)
    scoped_where = f"{where_sql} AND {_q(id_column)} = :record_id" if where_sql else f"WHERE {_q(id_column)} = :record_id"

    row = db.execute(
        text(
            f"SELECT {_q('pdf_file')} FROM {_q(TABLE_NAME)} "
            f"{scoped_where} LIMIT 1"
        ),
        {**params, "record_id": record_id},
    ).mappings().first()

    if row is None:
        raise HTTPException(status_code=404, detail="CVIData row not found")

    pdf_file = row.get("pdf_file")
    if not pdf_file:
        raise HTTPException(status_code=404, detail="No PDF linked to this row")

    candidate = _resolve_pdf_candidate(pdf_file)
    base = PDF_ROOT.resolve()

    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid PDF path") from exc

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"PDF not found: {candidate}")

    return FileResponse(
        path=str(candidate),
        media_type="application/pdf",
        filename=candidate.name,
        content_disposition_type="inline",
    )
