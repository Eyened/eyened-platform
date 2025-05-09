
from huey import RedisHuey
import os
import logging
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('eyened.huey')

# Initialize huey with Redis storage
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', 6379))
huey = RedisHuey(
    'eyened-tasks',
    host=redis_host,
    port=redis_port,
)

@huey.task()
@huey.lock_task('inference-lock')
def task_run_inference():
    """
    Run inference on images in a background task.
    
    Args:
        config: Configuration dictionary
        device: Device to run inference on (None for auto-selection)
    """
    from eyened_orm.utils.config import EyenedORMConfig
    from eyened_orm.inference.inference import run_inference
    from eyened_orm.db import DBManager
    logger.info(f"Starting inference task")

    config = EyenedORMConfig()
    DBManager.init(config)
    session = DBManager.get_session()
    
    run_inference(session, device=None, cfi_cache_path=None)
    session.close()
    logger.info("Inference task completed successfully")
    return True

@huey.task()
@huey.lock_task('update-thumbnails-lock') 
def task_update_thumbnails(print_errors=False):
    """
    Update thumbnails for images in a background task.
    
    Args:
        config: Configuration dictionary
    """
    from eyened_orm.utils.config import EyenedORMConfig
    from eyened_orm.importer.thumbnails import update_thumbnails
    from eyened_orm.db import DBManager
    logger.info(f"Starting thumbnail update task")

    config = EyenedORMConfig()
    DBManager.init(config)
    session = DBManager.get_session()
    
    update_thumbnails(
        session, 
        thumbnails_path='/storage/thumbnails', 
        secret_key= config.secret_key,
        print_errors=True
    )
    session.close()
    logger.info("Thumbnail update task completed successfully")
    return True
