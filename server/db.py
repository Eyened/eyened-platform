from eyened_orm import Database

from server.config import settings

# The one tuned Database in the codebase. Every other construction site -- the
# eorm CLI and the five per-job builds in server/utils/tasks.py -- keeps the
# conservative constructor defaults, because each of those is its own engine
# and its own pool.
database = Database(
    pool_size=settings.pool_size,
    max_overflow=settings.max_overflow,
)


def get_db():
    """Request-scoped transaction boundary: commit on success, roll back and
    re-raise on exception (python-resource-management Pattern 3). Repositories
    flush; this is the single commit for the request."""
    with database.get_session() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
