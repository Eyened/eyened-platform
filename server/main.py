import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from routes import annotations, api, auth, form_annotations, instances, tasks
from routes.config import settings
from routes.db import get_db
from utils.init_annotation_types import init_annotation_types
app_api = FastAPI(title="Eyened API")
app_api.include_router(auth.router)
app_api.include_router(instances.router)
app_api.include_router(api.router)
app_api.include_router(annotations.router)
app_api.include_router(form_annotations.router)
app_api.include_router(tasks.router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # before startup
    try:
        session = next(get_db())
        init_annotation_types(session)
    except Exception as e:
        print(f"Error initializing annotation types: {e}")
    finally:
        session.close()
    yield
    # after shutdown


app = FastAPI(lifespan=lifespan)

app.mount("/api", app_api)


if settings.viewer_env == "production":

    @app.get("/{path:path}")  # Catch-all route for file serving
    async def catch_all(path: str):
        file_path = os.path.join("/client/build", path)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)  # Serve existing file
        return FileResponse(os.path.join("/client/build", "index.html"))
