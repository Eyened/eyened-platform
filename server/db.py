from eyened_orm import Database

database = Database()
def get_db():
    with database.get_session() as session:
        yield session