import logging

from huey import RedisHuey

from server.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("eyened.huey")

# Initialize huey with Redis storage
huey = RedisHuey(
    "eyened-tasks",
    host=settings.redis.host,
    port=settings.redis.port,
)


@huey.task()
@huey.lock_task("inference-lock")
def task_run_inference():
    """
    Run inference on images in a background task.

    Args:
        device: Device to run inference on (None for auto-selection)
    """
    from eyened_orm.inference.inference import run_inference
    from eyened_orm import Database

    logger.info(f"Starting inference task")

    database = Database(settings.to_orm_config())

    with database.get_session() as session:
        # Use session for database operations

        run_inference(session, device=None)
    logger.info("Inference task completed successfully")
    return True


@huey.task()
@huey.lock_task("update-thumbnails-lock")
def task_update_thumbnails(print_errors=False):
    """
    Update thumbnails for images in a background task.
    """
    from eyened_orm.importer.thumbnails import update_thumbnails
    from eyened_orm import Database

    logger.info(f"Starting thumbnail update task")

    database = Database(settings.to_orm_config())

    with database.get_session() as session:
        update_thumbnails(
            session,
            thumbnails_path="/storage/thumbnails",
            secret_key=settings.secret_key_value,
            print_errors=True,
        )
    session.close()
    logger.info("Thumbnail update task completed successfully")
    return True
