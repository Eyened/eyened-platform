import logging
import sys
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
from server.config import get_redis_connection, settings
from server.services.exceptions import register_exception_handlers

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

register_exception_handlers(app_api)


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


def configure_audit_logging() -> None:
    """Route the eyened.audit logger to stdout as JSON, isolated from app logs.

    Compliance is never debug-gated: audit is always INFO. App/debug logs stay on
    stderr via logging.basicConfig().
    """
    audit = logging.getLogger("eyened.audit")
    audit.setLevel(settings.db_log.level)
    audit.propagate = False
    if not any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout
        for h in audit.handlers
    ):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        audit.addHandler(handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up with settings:")
    print(settings)

    if settings.public_auth_disabled:
        print("WARNING: PUBLIC_AUTH_DISABLED is enabled; authentication is bypassed")

    # before startup
    logging.basicConfig()
    if settings.debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
        logging.getLogger("server").setLevel(logging.DEBUG)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("server").setLevel(logging.INFO)

    # Audit events go to stdout as JSON; app/debug logs stay on stderr.
    configure_audit_logging()

    yield
    # after shutdown


app = FastAPI(lifespan=lifespan)

app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_minimum_size)

app.mount("/api", app_api)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


from rq import Queue

redis_conn = get_redis_connection()
queue = Queue("default", connection=redis_conn)

# Fallback when ``enqueue(..., job_timeout=...)`` is omitted (RQ default is 180s).
_QUEUE_DEFAULT_TIMEOUTS: dict[str, int] = {
    "layer-segmentation": 600,
}


def get_rq_queue(name: str) -> Queue:
    """Named RQ queue (e.g. ``cfi-roi`` for CFI ROI jobs)."""
    default_timeout = _QUEUE_DEFAULT_TIMEOUTS.get(name)
    return Queue(name, connection=redis_conn, default_timeout=default_timeout)