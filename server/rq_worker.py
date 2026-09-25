"""RQ worker process.

Queues are configured via ``EYENED_RQ_WORKER_QUEUES`` (comma-separated), e.g.:

- Full GPU stack: ``default,cfi-roi,cfi-keypoints,cfi-odfd,cfi-quality``
- Slim ROI-only image: ``cfi-roi``

Run from repo root::

    PYTHONPATH=. python -m server.rq_worker
"""

from rq import Worker

from eyened_orm.data_access import load_storage_mounts
from server.config import get_redis_connection, settings


def main() -> None:
    # A worker reads image data straight off the dataset bind mounts. Without
    # them it starts, takes jobs and fails every one of them in its own log,
    # with every container still showing as running -- no worker declares a
    # healthcheck, so `docker compose ps` shows nothing wrong. Checked before
    # the Redis connection so a misconfigured stack dies on its configuration.
    missing = sorted(
        f"{key} -> {path}"
        for key, path in load_storage_mounts().items()
        if not path.is_dir()
    )
    if missing:
        raise RuntimeError(
            "EYENED_STORAGE_MOUNTS names paths this container cannot see: "
            + ", ".join(missing)
            + ". With compose.workers.yaml in COMPOSE_FILE, uncomment the "
            "worker entries in compose.storage.yaml."
        )
    conn = get_redis_connection()
    names = [
        q.strip()
        for q in settings.rq.worker_queues.split(",")
        if q.strip()
    ]
    if not names:
        raise RuntimeError("EYENED_RQ_WORKER_QUEUES is empty")
    w = Worker(names, connection=conn)
    w.work()


if __name__ == "__main__":
    main()
