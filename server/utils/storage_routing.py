from typing import Optional

from fastapi import Response


def build_object_path(object_prefix: Optional[str], object_key: str) -> str:
    if object_prefix:
        return f"{object_prefix.rstrip('/')}/{object_key.lstrip('/')}"
    return object_key.lstrip("/")


def build_storage_redirect_response(
    object_prefix: Optional[str],
    object_key: str,
    base_path: str,
) -> Response:
    base = base_path if base_path.endswith("/") else f"{base_path}/"
    object_path = build_object_path(object_prefix, object_key)
    response = Response()
    response.headers["X-Accel-Redirect"] = f"{base}{object_path}"
    print("x-accel-redirect =>", f"{base}{object_path}")
    return response
