"""The models must declare the server-side semantics the database actually has.

The migrations are generated from the models, so a schema built from them is
only as correct as they are. `mapped_column(onupdate=...)` is a Python-side
hook that renders no DDL -- relying on it left five DateModified columns
undeclared, and any install built from orm_baseline diverged from dev.

`alembic check` cannot replace these: it proves the models and the migrations
*agree*, so it stays green if both lose the clause.
"""

import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from eyened_orm.base import Base

DATE_MODIFIED = ["AnnotationData", "FormAnnotation", "ImageInstance", "ImageStorage", "Segmentation"]


@pytest.mark.parametrize("table", DATE_MODIFIED)
def test_date_modified_is_maintained_by_mysql_on_every_write(table):
    """Without the ON UPDATE half only writes through a mapped class maintain
    the column; the importer, the CLI and raw SQL silently stop."""
    ddl = str(CreateTable(Base.metadata.tables[table]).compile(dialect=mysql.dialect()))
    # Identifiers come back backtick-quoted -- these column names are mixed case.
    line = next(line for line in ddl.splitlines() if "`DateModified`" in line)
    assert "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP" in line


def test_no_model_declares_the_noisy_now_spelling():
    """func.now() compiles under the MySQL dialect to unparenthesised `now()`
    (measured: `DATETIME DEFAULT now()`), and alembic strips only a trailing
    `()` when comparing -- reducing it to `now`, which can never text-match a
    reflected `current_timestamp`. So compare_server_default reports a false
    positive on every column that uses it, disabling the gate while looking
    correct. Same behaviour, different literal, which is why it survives
    review."""
    noisy = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.server_default is not None
        and "now()" in str(getattr(column.server_default, "arg", "")).lower()
    ]
    assert noisy == [], f"these render as now() and can never match a reflected current_timestamp: {noisy}"
