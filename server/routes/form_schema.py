from fastapi import APIRouter, Depends

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_main import FormSchemaGET
from ..services.form_schema_service import FormSchemaService, get_form_schema_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/form-schemas", response_model=list[FormSchemaGET])
async def list_form_schemas(
    service: FormSchemaService = Depends(get_form_schema_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return all form schemas."""
    rows = service.list_form_schemas()
    return [DTOConverter.form_schema_to_get(s) for s in rows]


@router.get("/form-schemas/{form_schema_id}", response_model=FormSchemaGET)
async def get_form_schema(
    form_schema_id: int,
    service: FormSchemaService = Depends(get_form_schema_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    schema = service.get_form_schema(form_schema_id)
    return DTOConverter.form_schema_to_get(schema)
