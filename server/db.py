from eyened_orm import DBManager

from .config import settings

config = {
    "database": settings.database,
    "annotations_path": settings.annotations_path
}

DBManager.init(config)


def get_db():
    with DBManager.yield_session() as db:
        yield db
