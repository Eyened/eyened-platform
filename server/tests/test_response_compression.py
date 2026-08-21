"""Responses below 1 MB were shipping uncompressed.

GZipMiddleware is installed on `app` (not the mounted `app_api`), so these
tests drive `app` and address routes under /api.
"""
from __future__ import annotations

import gzip
import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient


class _Feature:
    """Every attribute DTOConverter.feature_to_get reads, and no more."""

    def __init__(self, i: int) -> None:
        self.FeatureID = i
        self.FeatureName = f"feature-with-a-reasonably-long-name-{i}"
        self.subfeature_ids_list: list[int] = []
        self.subfeatures: dict[int, str] = {}
        self.DateInserted = datetime(2026, 1, 1)


class _ManyFeaturesService:
    """Returns enough features that the JSON comfortably exceeds 500 bytes."""

    def list_features(self, with_counts: bool = False):
        return [_Feature(i) for i in range(50)], {}


@pytest.fixture()
def app_client():
    from server.main import app, app_api
    from server.routes.auth import CurrentUser, get_current_user
    from server.services.feature_service import get_feature_service

    overrides = {
        get_feature_service: lambda: _ManyFeaturesService(),
        get_current_user: lambda: CurrentUser(creator_id=1, username="tester"),
    }
    app_api.dependency_overrides.update(overrides)
    # No context manager: entering it would run `app`'s lifespan, which this
    # test does not need.
    yield TestClient(app)
    for dep in overrides:
        app_api.dependency_overrides.pop(dep, None)


def test_a_small_json_response_is_compressed(app_client):
    """The band between 500 B and 1 MB is where every list response lives."""
    r = app_client.get("/api/features", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


def test_a_tiny_response_is_not_compressed(app_client):
    """500 bytes is a floor, not "compress everything"."""
    r = app_client.get("/health", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") is None


def test_a_pre_encoded_response_is_not_double_compressed():
    """Segmentation payloads set Content-Encoding themselves.

    GZipMiddleware records content_encoding_set (starlette/middleware/gzip.py)
    and skips such a response. Pinned because lowering the threshold is exactly
    what would expose a regression: the payload is deliberately incompressible
    so the ENCODED body clears the floor -- otherwise the size skip fires and
    the test proves nothing.
    """
    from fastapi import FastAPI
    from starlette.middleware.gzip import GZipMiddleware
    from starlette.responses import Response as StarletteResponse

    from server.config import settings

    payload = os.urandom(5000)
    probe = FastAPI()
    probe.add_middleware(GZipMiddleware, minimum_size=settings.gzip_minimum_size)

    # The middleware measures the ALREADY-COMPRESSED body, not the input.
    # Random bytes are incompressible, so this stays above the floor. With a
    # repetitive payload it compresses to ~40 bytes, the middleware skips on
    # SIZE, and this test passes without ever reaching the content-encoding
    # check it exists to verify.
    body = gzip.compress(payload)
    assert len(body) > settings.gzip_minimum_size

    @probe.get("/pre-encoded")
    def pre_encoded():
        return StarletteResponse(
            content=body,
            media_type="application/octet-stream",
            headers={"Content-Encoding": "gzip"},
        )

    r = TestClient(probe).get("/pre-encoded", headers={"Accept-Encoding": "gzip"})
    # httpx decodes exactly one gzip layer. Had the middleware added a second,
    # this would still be compressed bytes rather than the payload.
    assert r.content == payload
