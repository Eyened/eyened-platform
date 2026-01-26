from eyened_orm import Database

from server.config import settings

database = Database(settings.to_orm_config())

def get_db():
    with database.get_session() as session:
        yield session