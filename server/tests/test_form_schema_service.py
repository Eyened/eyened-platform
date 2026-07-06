import pytest

from eyened_orm import FormSchema
from eyened_orm.repositories.form_schema_repository import FormSchemaRepository

from server.services.exceptions import NotFoundError
from server.services.form_schema_service import FormSchemaService


def test_list_form_schemas_returns_rows_in_order(session):
    # The service hands back the repository's rows, order intact.
    session.add_all([FormSchema(SchemaName="Zeta"), FormSchema(SchemaName="Alpha")])
    session.flush()

    service = FormSchemaService(FormSchemaRepository())
    result = service.list_form_schemas(session)

    assert [s.SchemaName for s in result] == ["Alpha", "Zeta"]


def test_get_form_schema_returns_the_schema(session):
    # An existing schema is returned by the service unchanged.
    schema = FormSchema(SchemaName="Alpha")
    session.add(schema)
    session.flush()

    service = FormSchemaService(FormSchemaRepository())
    result = service.get_form_schema(session, schema.FormSchemaID)

    assert result.SchemaName == "Alpha"


def test_get_form_schema_unknown_id_raises_not_found(session):
    # A missing schema makes the service raise NotFoundError (-> 404 via handler).
    service = FormSchemaService(FormSchemaRepository())

    with pytest.raises(NotFoundError):
        service.get_form_schema(session, 999_999)
