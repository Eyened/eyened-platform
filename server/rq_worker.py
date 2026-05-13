"""RQ worker process.

Queues are configured via ``EYENED_RQ_WORKER_QUEUES`` (comma-separated), e.g.:

- Full GPU stack: ``default,cfi-roi,cfi-keypoints,cfi-odfd,cfi-quality``
- Slim ROI-only image: ``cfi-roi``

Run from repo root::

    PYTHONPATH=. python -m server.rq_worker
"""

from rq import Worker

from server.config import get_redis_connection, settings


def main() -> None:
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
