import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware
from sqlalchemy.exc import SQLAlchemyError

from server.routes import (
    auth,
    import_api,
    instances,
    segmentations,
    form_schema,
    form_annotations,
    feature,
    tag,
    task,
    subtask,
    search,
    devices,
    studies,
    patients,
)
from server.utils.db_logging import init_db_logger
from server.config import settings

app_api = FastAPI(title="Eyened API")
app_api.include_router(auth.router)
app_api.include_router(instances.router)
app_api.include_router(segmentations.router)
app_api.include_router(import_api.router)
app_api.include_router(form_annotations.router)
app_api.include_router(search.router)
app_api.include_router(form_schema.router)
app_api.include_router(feature.router)
app_api.include_router(tag.router)
app_api.include_router(task.router)
app_api.include_router(subtask.router)
app_api.include_router(devices.router)
app_api.include_router(studies.router)
app_api.include_router(patients.router)


### Exception handlers
@app_api.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app_api.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    if settings.debug:
        # print stack trace
        traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "A database error occurred."},
    )


@app_api.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    if settings.debug:
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

    if settings.public_auth_disabled:
        print("WARNING: PUBLIC_AUTH_DISABLED is enabled; authentication is bypassed")

    # # before startup
    logging.basicConfig()
    if settings.debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Initialize database modification logger
    init_db_logger(settings)

    yield
    # after shutdown


app = FastAPI(lifespan=lifespan)

app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_minimum_size)

app.mount("/api", app_api)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


from redis import Redis
from rq import Queue
redis_conn = Redis(host='redis', port=6379)
queue = Queue("default", connection=redis_conn)