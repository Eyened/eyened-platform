"""restrict tag deletes that would cascade into project data

Revision ID: c3f5a2b81d94
Revises: a1d1700000a1
Create Date: 2026-07-30

Flips the five annotation-link TagID foreign keys from ON DELETE CASCADE to
ON DELETE RESTRICT, so deleting a tag can no longer destroy applied-tag
annotation data on any path -- HTTP API, CLI, eorm, importer or raw SQL
(spec §3.2.1). CreatorTag is deliberately excluded: a star is a personal
preference, so it must keep cascading and must never block a delete.

MySQL auto-names these constraints (StudyTag_ibfk_2, ...) and the numbering
depends on creation order, so the names are discovered from the live schema
rather than hardcoded.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3f5a2b81d94"
down_revision: Union[str, None] = "a1d1700000a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The five annotation-data links. CreatorTag is NOT in this list, by design.
LINK_TABLES = (
    "StudyTag",
    "ImageInstanceTag",
    "AnnotationTag",
    "SegmentationTag",
    "FormAnnotationTag",
)


def _tagid_fk_name(inspector: sa.Inspector, table: str) -> str:
    """Return the name of ``table``'s TagID -> Tag foreign key."""
    for fk in inspector.get_foreign_keys(table):
        if fk["referred_table"] == "Tag" and fk["constrained_columns"] == ["TagID"]:
            name = fk.get("name")
            if not name:
                raise RuntimeError(
                    f"{table}: TagID foreign key is unnamed; cannot alter it"
                )
            return name
    raise RuntimeError(f"{table}: no TagID -> Tag foreign key found")


def _set_tagid_ondelete(action: str) -> None:
    """Recreate each link table's TagID FK with the given ON DELETE action."""
    inspector = sa.inspect(op.get_bind())
    for table in LINK_TABLES:
        name = _tagid_fk_name(inspector, table)
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name, table, "Tag", ["TagID"], ["TagID"], ondelete=action
        )


def upgrade() -> None:
    _set_tagid_ondelete("RESTRICT")


def downgrade() -> None:
    _set_tagid_ondelete("CASCADE")
