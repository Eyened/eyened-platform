from eyened_orm import DBManager

from .config import settings

if settings.db_engine_string is not None:
    database = {'conn_string': settings.db_engine_string}
else:
    database = settings.database

config = {
    "database": database,
    "annotations_path": settings.annotations_path
}

DBManager.init(config)


def get_db():
    with DBManager.yield_session() as db:
        yield db
