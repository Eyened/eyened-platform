from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from eyened_orm import FormSchema
from ..db import get_db
from .auth import CurrentUser, get_current_user
from ..dtos.dtos_main import FormSchemaGET
from ..dtos.dto_converter import DTOConverter

router = APIRouter()

@router.get("/form-schemas", response_model=list[FormSchemaGET])
async def list_form_schemas(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    rows = db.scalars(select(FormSchema).order_by(FormSchema.SchemaName.asc())).all()
    return [DTOConverter.form_schema_to_get(s) for s in rows]

@router.get("/form-schemas/{form_schema_id}", response_model=FormSchemaGET)
async def get_form_schema(form_schema_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    schema = db.get(FormSchema, form_schema_id)
    if not schema:
        raise HTTPException(404, "FormSchema not found")
    return DTOConverter.form_schema_to_get(schema)
