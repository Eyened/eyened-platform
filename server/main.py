import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse

from server.config import settings
from server.db import get_db
from server.routes import (
    api,
    auth,
    crud_resources,
    form_annotations,
    import_api,
    instances,
    segmentations,
    tasks,
)
from server.utils.database_init import (
    create_database,
    init_admin,
    init_task_states,
    init_other_objects,
)

app_api = FastAPI(title="Eyened API")
app_api.include_router(auth.router)
app_api.include_router(instances.router)
app_api.include_router(api.router)
app_api.include_router(segmentations.router)
#app_api.include_router(form_annotations.router)
#app_api.include_router(tasks.router)
app_api.include_router(import_api.router)

app_api.include_router(crud_resources.router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up with settings:")
    print(settings)

    if os.environ.get("DB_ROOT_PASSWORD"):
        try:
            # create database tables and user if they don't exist
            create_database()
        except Exception as e:
            raise RuntimeError(f"Error creating database: {e}") from e
    else:
        print("DB_ROOT_PASSWORD is not set, skipping database creation")

    # before startup
    try:
        session = next(get_db())
        # initialize admin user
        init_admin(session)
        # initialize other objects
        init_other_objects(session)
        # initialize task states
        init_task_states(session)
    except Exception as e:
        raise RuntimeError(f"Error initializing database objects") from e
    finally:
        session.close()
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
