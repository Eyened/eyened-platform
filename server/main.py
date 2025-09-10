import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from server.config import settings
from server.routes import (
    auth,
    import_api,
    instances,
    segmentations,
    form_schema,
    feature,
    tag,
    task,
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
app_api.include_router(segmentations.router)
app_api.include_router(import_api.router)
app_api.include_router(form_schema.router)
app_api.include_router(feature.router)
app_api.include_router(tag.router)
app_api.include_router(task.router)


### Exception handlers
@app_api.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

@app_api.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    if settings.environment == 'development':
        # print stack trace
        traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "A database error occurred."},
    )

@app_api.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    if settings.environment == 'development':
        # print stack trace
        traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )



@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up with settings:")
    
    print(settings)
    if settings.auth_disabled:
        print("WARNING: AUTH_DISABLED is enabled; authentication is bypassed")

    if settings.database_root_password is not None:
        try:
            # create database tables and user if they don't exist
            create_database()
        except Exception as e:
            raise RuntimeError(f"Error creating database: {e}") from e
    else:
        print("DATABASE_ROOT_PASSWORD is not set, skipping database creation")

    # before startup
    
    
    db = Database(settings)

    

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



