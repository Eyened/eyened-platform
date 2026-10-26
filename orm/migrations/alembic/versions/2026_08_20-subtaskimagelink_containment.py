"""Copy TaskID and ProjectID onto SubTaskImageLink and point them at TaskProject.

Revision ID: 2db0e63195db
Revises: b45090e1544e
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2db0e63195db"
down_revision: Union[str, None] = "b45090e1544e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_INDEXES = (
    "ix_SubTaskImageLink_Image_SubTask",
    "fk_SubTaskImageLink_SubTask1_idx",
    "fk_SubTaskImageLink_ImageInstance1_idx",
)


def _fk_name(table: str, column: str, referred_table: str) -> str:
    """Return the name of the one foreign key from table.column to referred_table."""
    names = op.get_bind().execute(
        sa.text(
            "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE"
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
            " AND COLUMN_NAME = :column AND REFERENCED_TABLE_NAME = :referred_table"
        ),
        {"table": table, "column": column, "referred_table": referred_table},
    ).scalars().all()
    if len(names) != 1:
        raise RuntimeError(
            f"expected one foreign key {table}.{column} -> {referred_table}, found {names}"
        )
    return names[0]


def _existing_indexes(table: str, names: Sequence[str]) -> list[str]:
    """Return the stored names of the indexes on table that match names, ignoring case."""
    wanted = {name.lower() for name in names}
    found = op.get_bind().execute(
        sa.text(
            "SELECT DISTINCT INDEX_NAME FROM information_schema.STATISTICS"
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
        ),
        {"table": table},
    ).scalars().all()
    return [name for name in found if name.lower() in wanted]


def upgrade() -> None:
    op.execute("SET SESSION foreign_key_checks = 1")
    op.execute(
        "SET SESSION sql_mode = "
        "CONCAT_WS(',', NULLIF(@@SESSION.sql_mode, ''), 'STRICT_ALL_TABLES')"
    )
    # Look up every name that varies between databases before the first ALTER.
    fk_link_image = _fk_name("SubTaskImageLink", "ImageInstanceID", "ImageInstance")
    fk_link_subtask = _fk_name("SubTaskImageLink", "SubTaskID", "SubTask")
    drops = [
        f"DROP FOREIGN KEY `{fk_link_subtask}`",
        f"DROP FOREIGN KEY `{fk_link_image}`",
    ] + [f"DROP INDEX `{name}`" for name in _existing_indexes("SubTaskImageLink", OLD_INDEXES)]

    op.execute("""
        ALTER TABLE SubTaskImageLink
            ADD COLUMN TaskID INT NULL,
            ADD COLUMN ProjectID INT NULL
    """)
    op.execute("""
        UPDATE SubTaskImageLink l
        JOIN SubTask st ON st.SubTaskID = l.SubTaskID
        JOIN ImageInstance ii ON ii.ImageInstanceID = l.ImageInstanceID
        SET l.TaskID = st.TaskID, l.ProjectID = ii.ProjectID
    """)
    op.execute("""
        ALTER TABLE SubTask
        ADD UNIQUE INDEX uq_SubTask_SubTask_Task (SubTaskID, TaskID)
    """)
    # fk_SubTaskImageLink_TaskProject rejects any link whose task has not
    # declared that project. MODIFY fails if the UPDATE missed a row.
    op.execute(f"""
        ALTER TABLE SubTaskImageLink
            MODIFY TaskID INT NOT NULL,
            MODIFY ProjectID INT NOT NULL,
            ADD INDEX ix_SubTaskImageLink_Image_Project (ImageInstanceID, ProjectID, SubTaskID),
            ADD INDEX ix_SubTaskImageLink_SubTask_Task (SubTaskID, TaskID),
            ADD INDEX ix_SubTaskImageLink_Task_Project (TaskID, ProjectID),
            ADD CONSTRAINT fk_SubTaskImageLink_SubTask_Task
                FOREIGN KEY (SubTaskID, TaskID)
                REFERENCES SubTask (SubTaskID, TaskID)
                ON UPDATE CASCADE ON DELETE CASCADE,
            ADD CONSTRAINT fk_SubTaskImageLink_Image_Project
                FOREIGN KEY (ImageInstanceID, ProjectID)
                REFERENCES ImageInstance (ImageInstanceID, ProjectID)
                ON UPDATE CASCADE ON DELETE CASCADE,
            ADD CONSTRAINT fk_SubTaskImageLink_TaskProject
                FOREIGN KEY (TaskID, ProjectID)
                REFERENCES TaskProject (TaskID, ProjectID),
            {", ".join(drops)}
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE SubTaskImageLink
            DROP FOREIGN KEY fk_SubTaskImageLink_SubTask_Task,
            DROP FOREIGN KEY fk_SubTaskImageLink_Image_Project,
            DROP FOREIGN KEY fk_SubTaskImageLink_TaskProject,
            DROP INDEX ix_SubTaskImageLink_Image_Project,
            DROP INDEX ix_SubTaskImageLink_SubTask_Task,
            DROP INDEX ix_SubTaskImageLink_Task_Project,
            DROP COLUMN TaskID,
            DROP COLUMN ProjectID
    """)
    op.execute("ALTER TABLE SubTask DROP INDEX uq_SubTask_SubTask_Task")
    op.execute("""
        ALTER TABLE SubTaskImageLink
            ADD CONSTRAINT fk_SubTaskImageLink_SubTask_single
                FOREIGN KEY (SubTaskID) REFERENCES SubTask (SubTaskID) ON DELETE CASCADE,
            ADD CONSTRAINT fk_SubTaskImageLink_Image_single
                FOREIGN KEY (ImageInstanceID) REFERENCES ImageInstance (ImageInstanceID)
                ON DELETE CASCADE
    """)
