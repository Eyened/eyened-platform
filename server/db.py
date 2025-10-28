from eyened_orm import Database
from eyened_orm.utils.config import load_config

config = load_config()
database = Database(config)


def get_db():
    with database.get_session() as session:
        yield session
