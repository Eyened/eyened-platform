from eyened_orm import Database

database = Database()


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
