import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse

from server.config import settings
from server.routes import (
    api,
    auth,
    crud_resources,
    import_api,
    instances,
    segmentations,
)
from server.utils.database_init import (
    create_database,
    init_admin,
    init_task_states,
)
from eyened_orm import Database

app_api = FastAPI(title="Eyened API")
app_api.include_router(auth.router)
app_api.include_router(instances.router)
app_api.include_router(api.router)
app_api.include_router(segmentations.router)
app_api.include_router(import_api.router)

app_api.include_router(crud_resources.router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up with settings:")
    print(settings)

    if os.environ.get("DATABASE_ROOT_PASSWORD"):
        try:
            # create database tables and user if they don't exist
            create_database()
        except Exception as e:
            raise RuntimeError(f"Error creating database: {e}") from e
    else:
        print("DATABASE_ROOT_PASSWORD is not set, skipping database creation")

    # before startup
    db = Database()
    with db.get_session() as session:
        init_admin(session)
        init_task_states(session)
        


    yield
    # after shutdown




app = FastAPI(lifespan=lifespan)

app.mount("/api", app_api)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/{path:path}")  # Catch-all route for file serving
async def catch_all(path: str):
    file_path = os.path.join("/client/build", path)

    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)  # Serve existing file
    return FileResponse(os.path.join("/client/build", "index.html"))
