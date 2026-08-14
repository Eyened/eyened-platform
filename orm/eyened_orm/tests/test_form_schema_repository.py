from eyened_orm import FormSchema
from eyened_orm.repositories.form_schema_repository import FormSchemaRepository


def test_list_all_orders_by_schema_name(session):
    """list_all returns every schema sorted by name ascending."""
    session.add_all(
        [
            FormSchema(SchemaName="Zeta"),
            FormSchema(SchemaName="Alpha"),
            FormSchema(SchemaName="Mu"),
        ]
    )
    session.flush()

    result = FormSchemaRepository(session).list_all()

    assert [s.SchemaName for s in result] == ["Alpha", "Mu", "Zeta"]


def test_get_by_id_returns_the_schema(session):
    """A known id returns that schema."""
    schema = FormSchema(SchemaName="Alpha")
    session.add(schema)
    session.flush()

    result = FormSchemaRepository(session).get_by_id(schema.FormSchemaID)

    assert result is not None
    assert result.SchemaName == "Alpha"


def test_get_by_id_unknown_id_returns_none(session):
    """An unknown id returns None — the repository never raises for "not found"."""
    assert FormSchemaRepository(session).get_by_id(999_999) is None
