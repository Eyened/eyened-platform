from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from eyened_orm import Creator, SubTask
from eyened_orm.utils.db_users import create_user, disable_password, hash_password
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from ..db import get_db
from .auth import CurrentUser, get_current_user, require_admin

router = APIRouter(prefix="/management", tags=["management"])


class AdminUserCreate(BaseModel):
    username: str
    password: str
    role: Optional[int] = None


class AdminUserPatch(BaseModel):
    role: Optional[int] = None
    password: Optional[str] = None
    disable_password_login: Optional[bool] = None


class AdminUserResponse(BaseModel):
    id: int
    username: str
    role: Optional[int] = None
    is_human: bool


class CVIAssignmentRow(BaseModel):
    id: Any
    status: Optional[str] = None
    subtask_id: Optional[int] = None
    subtask_assignee_user_id: Optional[int] = None
    subtask_assignee_username: Optional[str] = None
    changes: Optional[int] = None


class CVIAssignmentResponse(BaseModel):
    rows: list[CVIAssignmentRow]
    total: int


class AssignCVIUserRequest(BaseModel):
    subtask_id: Optional[int] = None


TABLE_NAME = "CVIData"


def _q(identifier: str) -> str:
    return f"`{identifier.replace('`', '``')}`"


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _cvi_table_info(db: Session) -> tuple[str, list[str]]:
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


def _first_existing(columns: list[str], candidates: list[str]) -> Optional[str]:
    for name in candidates:
        if name in columns:
            return name
    return None


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    require_admin(current_user, db)
    users = db.query(Creator).order_by(Creator.CreatorName.asc()).all()
    return [
        AdminUserResponse(
            id=u.CreatorID,
            username=u.CreatorName,
            role=u.Role,
            is_human=bool(u.IsHuman),
        )
        for u in users
    ]


@router.post("/users", response_model=AdminUserResponse)
async def create_user_admin(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    require_admin(current_user, db)
    try:
        user = create_user(db, payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if payload.role is not None:
        user.Role = payload.role
        db.commit()
        db.refresh(user)

    return AdminUserResponse(
        id=user.CreatorID,
        username=user.CreatorName,
        role=user.Role,
        is_human=bool(user.IsHuman),
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def patch_user_admin(
    user_id: int,
    payload: AdminUserPatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    require_admin(current_user, db)
    user = db.get(Creator, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.role is not None:
        user.Role = payload.role
    if payload.password is not None:
        user.PasswordHash = hash_password(payload.password)
        user.Password = None
    if payload.disable_password_login:
        user.PasswordHash = disable_password(user.PasswordHash)
        user.Password = None

    db.commit()
    db.refresh(user)

    return AdminUserResponse(
        id=user.CreatorID,
        username=user.CreatorName,
        role=user.Role,
        is_human=bool(user.IsHuman),
    )


@router.delete("/users/{user_id}")
async def delete_user_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    require_admin(current_user, db)
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    user = db.get(Creator, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"status": "deleted"}


@router.get("/cvi/records", response_model=CVIAssignmentResponse)
async def list_cvi_records_for_assignment(
    limit: int = 100,
    offset: int = 0,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    require_admin(current_user, db)

    id_column, columns = _cvi_table_info(db)
    subtask_column = _first_existing(columns, ["SubTaskID", "subtask_id", "sub_task_id"])
    if subtask_column is None:
        raise HTTPException(status_code=400, detail="SubTaskID column not found in CVIData")

    status_column = _first_existing(columns, ["status", "visual_status"])
    changes_column = _first_existing(columns, ["changes"])
    search_column = _first_existing(columns, ["patient_name", "status", "visual_status", "patient_is", "is"])

    selected_cols = [id_column]
    for optional in [status_column, subtask_column, changes_column]:
        if optional and optional not in selected_cols:
            selected_cols.append(optional)

    selected = ", ".join(_q(c) for c in selected_cols)

    where = ""
    params: dict[str, Any] = {"limit": max(1, min(limit, 500)), "offset": max(0, offset)}
    if search and search_column:
        where = f" WHERE LOWER(COALESCE({_q(search_column)}, '')) LIKE :search"
        params["search"] = f"%{search.lower()}%"

    total_row = db.execute(
        text(f"SELECT COUNT(*) AS n FROM {_q(TABLE_NAME)}{where}"),
        {k: v for k, v in params.items() if k == "search"},
    ).mappings().first()
    total = int((total_row or {}).get("n", 0))

    rows = db.execute(
        text(
            f"SELECT {selected} FROM {_q(TABLE_NAME)}{where} "
            f"ORDER BY {_q(id_column)} ASC LIMIT :limit OFFSET :offset"
        ),
        params,
    ).mappings().all()

    subtask_ids = sorted({int(r[subtask_column]) for r in rows if r.get(subtask_column) not in (None, "")})
    creator_by_subtask_id: dict[int, Optional[int]] = {}
    if subtask_ids:
        subtask_rows = db.query(SubTask).filter(SubTask.SubTaskID.in_(subtask_ids)).all()
        creator_by_subtask_id = {
            int(r.SubTaskID): (int(r.CreatorID) if r.CreatorID is not None else None)
            for r in subtask_rows
        }

    creator_ids = sorted({cid for cid in creator_by_subtask_id.values() if cid is not None})
    usernames: dict[int, str] = {}
    if creator_ids:
        creator_rows = db.query(Creator).filter(Creator.CreatorID.in_(creator_ids)).all()
        usernames = {int(r.CreatorID): str(r.CreatorName) for r in creator_rows}

    response_rows = []
    for row in rows:
        raw_subtask_id = row.get(subtask_column)
        subtask_id_int = int(raw_subtask_id) if raw_subtask_id not in (None, "") else None
        assignee_user_id = creator_by_subtask_id.get(subtask_id_int) if subtask_id_int is not None else None
        response_rows.append(
            CVIAssignmentRow(
                id=_serialize_value(row.get(id_column)),
                status=_serialize_value(row.get(status_column)) if status_column else None,
                subtask_id=subtask_id_int,
                subtask_assignee_user_id=assignee_user_id,
                subtask_assignee_username=usernames.get(assignee_user_id) if assignee_user_id is not None else None,
                changes=_serialize_value(row.get(changes_column)) if changes_column else None,
            )
        )

    return CVIAssignmentResponse(rows=response_rows, total=total)


@router.patch("/cvi/records/{record_id}/assign")
async def assign_cvi_record_user(
    record_id: str,
    payload: AssignCVIUserRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    require_admin(current_user, db)

    id_column, columns = _cvi_table_info(db)
    subtask_column = _first_existing(columns, ["SubTaskID", "subtask_id", "sub_task_id"])
    if subtask_column is None:
        raise HTTPException(status_code=400, detail="SubTaskID column not found in CVIData")

    if payload.subtask_id is not None:
        subtask = db.execute(
            text("SELECT `SubTaskID` FROM `SubTask` WHERE `SubTaskID` = :subtask_id LIMIT 1"),
            {"subtask_id": payload.subtask_id},
        ).mappings().first()
        if subtask is None:
            raise HTTPException(status_code=404, detail="SubTask not found")

    db.execute(
        text(
            f"UPDATE {_q(TABLE_NAME)} SET {_q(subtask_column)} = :subtask_id "
            f"WHERE {_q(id_column)} = :record_id"
        ),
        {"subtask_id": payload.subtask_id, "record_id": record_id},
    )
    db.commit()

    return {"status": "ok"}
