"""A worker told about datasets it cannot see must die at boot, not at job time."""
from __future__ import annotations

import json

import pytest

from eyened_orm.data_access import load_storage_mounts
from server import rq_worker


@pytest.fixture(autouse=True)
def _clear_mount_cache():
    # load_storage_mounts is lru_cached, so a stale entry would leak into and
    # out of this test.
    load_storage_mounts.cache_clear()
    yield
    load_storage_mounts.cache_clear()


def test_main_refuses_to_start_when_a_mapped_dataset_is_absent(monkeypatch, tmp_path):
    """Without the bind mount the path is simply not there; say so and stop."""
    monkeypatch.setenv(
        "EYENED_STORAGE_MOUNTS", json.dumps({"cfi": str(tmp_path / "absent")})
    )
    # Without this the test is red only where Redis happens to be unreachable.
    # Where it resolves, a guard that regressed would reach Worker.work() and
    # block the suite forever instead of failing, consuming a real queue on the
    # way.
    monkeypatch.setattr(
        rq_worker, "get_redis_connection", lambda: pytest.fail("reached Redis")
    )

    with pytest.raises(RuntimeError, match="cfi"):
        rq_worker.main()
