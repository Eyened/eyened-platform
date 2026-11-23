"""The shared HTTP client that fetches external data sources."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import anyio
import httpxyz
from pydantic import TypeAdapter, ValidationError

from ..dtos.dtos_aux import NamedTables
from .exceptions import NotFoundError, UpstreamError

logger = logging.getLogger(__name__)

_named_tables = TypeAdapter(NamedTables)

# ASSUMPTION: 10 concurrent upstream calls per worker, 2 s to connect and 10 s
# for the whole call are enough for the sources sites configure today.
DATA_SOURCE_MAX_CONNECTIONS = 10
DATA_SOURCE_CONNECT_TIMEOUT = 2
DATA_SOURCE_TIMEOUT = 10

# Opened and closed by the app lifespan; a module holder because the lifespan
# runs on the main app while routes run on the mounted sub-app.
_client: httpxyz.AsyncClient | None = None


@asynccontextmanager
async def data_source_client_lifespan():
    """Open the shared client for the app's lifetime."""
    global _client
    _client = httpxyz.AsyncClient(
        limits=httpxyz.Limits(max_connections=DATA_SOURCE_MAX_CONNECTIONS),
        timeout=httpxyz.Timeout(DATA_SOURCE_TIMEOUT, connect=DATA_SOURCE_CONNECT_TIMEOUT),
    )
    try:
        yield
    finally:
        await _client.aclose()
        _client = None


def get_data_source_client() -> httpxyz.AsyncClient:
    """FastAPI dependency returning the shared client."""
    assert _client is not None, "data source client used outside the app lifespan"
    return _client


async def fetch_data_source(client: httpxyz.AsyncClient, name: str, url: str) -> NamedTables:
    """GET ``url`` for source ``name``; return its body as named tables.

    Raises:
        NotFoundError: If the upstream has no data (404).
        UpstreamError: If the upstream fails, does not answer in time, or
            returns something that is not named tables.
    """
    # The URL is not logged: it holds a patient identifier.
    try:
        with anyio.fail_after(DATA_SOURCE_TIMEOUT):
            response = await client.get(url)
    except TimeoutError:
        logger.warning("Data source %s timed out", name)
        raise UpstreamError(f"Data source {name} unavailable") from None
    except httpxyz.HTTPError as exc:
        logger.warning("Data source %s unreachable: %s", name, type(exc).__name__)
        raise UpstreamError(f"Data source {name} unavailable") from None
    if response.status_code == 404:
        raise NotFoundError(f"Data source {name} has no data for this study")
    if not response.is_success:
        logger.warning("Data source %s returned HTTP %s", name, response.status_code)
        raise UpstreamError(f"Data source {name} unavailable")
    try:
        return _named_tables.validate_json(response.content)
    except ValidationError:
        logger.warning("Data source %s returned data that is not named tables", name)
        raise UpstreamError(f"Data source {name} unavailable") from None
