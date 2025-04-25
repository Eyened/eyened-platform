from eyened_orm import DBManager

from .config import settings


DBManager.init(settings)


def get_db():
    with DBManager.yield_session() as db:
        yield db
