"""add Study.ProjectID and Series.ProjectID

Revision ID: 4eae42457fa2
Revises: d3ce100ab2b6
Create Date: 2026-08-20

Completes the denormalization chain Patient -> Study -> Series ->
ImageInstance. ImageInstance got its copy in d3ce100ab2b6; these two middle
links exist so the composite foreign keys can later hold each copy equal to
its parent's structurally, rather than leaving ImageInstance.ProjectID a cache
of a value it has no way to check.

Each column lands nullable, is backfilled in autocommitted chunks, and is only
then tightened to NOT NULL -- adding it NOT NULL outright fails on a table
with rows.

No index is created here: ProjectID is indexed as the trailing column of the
composite keys added with the composite foreign key, not on its own.

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


# revision identifiers, used by Alembic.
revision: str = '4eae42457fa2'
down_revision: Union[str, None] = 'd3ce100ab2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Deliberately copied from d3ce100ab2b6 rather than imported: a migration that
# imports from another one breaks the moment that other file is squashed away.
def _column_exists(conn: Connection, table: str, column: str) -> bool:
    """Make ADD COLUMN re-runnable. MySQL has no ADD COLUMN IF NOT EXISTS."""
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = :t AND COLUMN_NAME = :c"
            ),
            {"t": table, "c": column},
        ).scalar()
    )


# ``MODIFY ProjectID INT NOT NULL`` at the end of each table's turn is the only
# check that the backfill left no NULLs behind, and it only checks anything
# under a strict SQL mode: a non-strict server silently rewrites a residual
# NULL to 0, producing rows that no project scope will ever return and that the
# composite foreign key on (PatientID, ProjectID) later rejects. Nothing in
# this repository's server or client configuration sets sql_mode, so the
# migration has to assert it for itself.
_STRICT_MODES = ("STRICT_ALL_TABLES", "STRICT_TRANS_TABLES")


def _require_strict_sql_mode(conn: Connection) -> None:
    """Refuse to run unless a missed row would fail the tightening, not become 0."""
    if conn.dialect.name != "mysql":
        return
    sql_mode = conn.execute(sa.text("SELECT @@SESSION.sql_mode")).scalar() or ""
    if not {mode.strip() for mode in sql_mode.split(",")} & set(_STRICT_MODES):
        raise RuntimeError(
            "this migration requires a strict SQL mode. The session sql_mode is "
            f"{sql_mode!r}, which contains none of {', '.join(_STRICT_MODES)}. "
            "Without one, ALTER TABLE ... MODIFY ProjectID INT NOT NULL "
            "rewrites any row the backfill missed to ProjectID = 0 instead of "
            "failing. Set a strict sql_mode on the server or the connection, "
            "then re-run."
        )


# Study before Series: Series reads its project from Study.ProjectID, so the
# parent table's column has to exist and be filled first. This order is
# load-bearing -- do not reorder it for tidiness.
#
# Each table is carried all the way through (add, backfill, tighten) before the
# next one starts, so a failure in Series' turn leaves Study fully migrated,
# Series untouched or half-migrated, and alembic_version unmoved. That is why
# ADD COLUMN is guarded by _column_exists and the backfill is idempotent: a
# re-run is a no-op up to the point that failed. MySQL commits DDL implicitly,
# so there is no transaction that would have undone the first table's work.
_TABLES = (
    ("Study", "StudyID", "JOIN Patient p ON p.PatientID = t.PatientID"),
    ("Series", "SeriesID", "JOIN Study p ON p.StudyID = t.StudyID"),
)


def upgrade() -> None:
    conn = op.get_bind()
    # Before the first DDL statement of the whole migration, not once per
    # table: MySQL commits DDL implicitly, so a guard that raises after any
    # ADD COLUMN has run leaves the schema half changed.
    _require_strict_sql_mode(conn)
    for table, pk, parent_join in _TABLES:
        if not _column_exists(conn, table, "ProjectID"):
            op.execute(
                f"ALTER TABLE {table} ADD COLUMN ProjectID INT NULL, "
                "ALGORITHM=INPLACE, LOCK=NONE"
            )
        # The backfill is a plain UPDATE, so it gets none of the online
        # behaviour of the ADD COLUMN above and would otherwise hold row locks
        # on the whole table in one transaction. It runs inside an autocommit
        # block so that each chunk commits on its own. Committing this
        # migration's connection directly would do the same for the chunks but
        # deactivate the transaction alembic is holding open around the whole
        # run -- everything after it, including the UPDATE of alembic_version
        # that follows the last DDL, would autobegin a transaction nobody
        # commits and lose it at connection close, leaving the schema changed
        # and the revision never stamped.
        with context.get_context().autocommit_block():
            # The block swaps in a connection at AUTOCOMMIT isolation, so the
            # bind has to be re-fetched here rather than reused from above.
            conn = op.get_bind()
            lo = conn.execute(sa.text(f"SELECT MIN({pk}) FROM {table}")).scalar()
            hi = conn.execute(sa.text(f"SELECT MAX({pk}) FROM {table}")).scalar()
            step = 20_000
            # MIN/MAX are read once and the ADD COLUMN ran LOCK=NONE, so rows
            # inserted while this loop runs -- by code that does not yet carry
            # the listener -- land above `hi`, and a loop that stopped there
            # would never see them. The primary key is AUTO_INCREMENT, so those
            # rows can only ever be above it: re-reading MAX when the loop
            # reaches its end and continuing from where it stopped covers
            # exactly that window while keeping every statement inside one 20k
            # id range. A closing `WHERE ProjectID IS NULL` sweep would cover
            # the same rows, but with no index on ProjectID it scans the whole
            # table and X-locks every row it examines to find them, re-taking
            # the lock exposure the chunking exists to avoid -- and MySQL
            # rejects LIMIT on a multi-table UPDATE, so the bound has to come
            # from the id range. Each catch-up pass only covers what arrived
            # during the previous one, so the passes shrink; the counter makes
            # the loop terminate even if writes never quiet down, and the
            # MODIFY ... NOT NULL below is what refuses to let a row the passes
            # did not reach through.
            catchups_left = 5
            while lo is not None and lo <= hi:
                # Clamped to `hi`, never `lo + step - 1` outright: a window
                # that reached past the highest id seen so far would be marked
                # done while rows were still landing inside it, and `lo` would
                # step over them.
                chunk_hi = min(lo + step - 1, hi)
                conn.execute(
                    sa.text(
                        f"UPDATE {table} t {parent_join} "
                        "SET t.ProjectID = p.ProjectID "
                        f"WHERE t.{pk} BETWEEN :lo AND :hi"
                    ),
                    {"lo": lo, "hi": chunk_hi},
                )
                lo = chunk_hi + 1
                if lo > hi and catchups_left:
                    catchups_left -= 1
                    hi = conn.execute(
                        sa.text(f"SELECT MAX({pk}) FROM {table}")
                    ).scalar()
        op.execute(
            f"ALTER TABLE {table} MODIFY ProjectID INT NOT NULL, "
            "ALGORITHM=INPLACE, LOCK=NONE"
        )


def downgrade() -> None:
    for table in ("Series", "Study"):
        op.execute(
            f"ALTER TABLE {table} DROP COLUMN ProjectID, "
            "ALGORITHM=INPLACE, LOCK=NONE"
        )
