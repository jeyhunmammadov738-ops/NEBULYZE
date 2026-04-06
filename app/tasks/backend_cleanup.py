import os
import time
import shutil
import logging
from .celery_app import celery_app

# Circuit breakers
from ..circuit_breakers import redis_breaker

logger = logging.getLogger(__name__)

TEMP_DIRS = ["temp_uploads", "temp_files"]
MAX_AGE_SECONDS = 1800 # 30 minutes (Oracle VPS aggressive cleanup)

@celery_app.task(name="app.tasks.backend_cleanup.auto_cleanup_task")
def auto_cleanup_task():
    """
    Periodic task to remove files older than 1 hour from temp directories.
    Prevents VPS disk exhaustion.
    """
    logger.info("Starting aggressive temporary file cleanup...")
    now = time.time()
    count = 0
    
    for directory in TEMP_DIRS:
        if not os.path.exists(directory):
            continue
            
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                # Check file age
                if os.path.exists(file_path):
                    if now - os.path.getmtime(file_path) > MAX_AGE_SECONDS:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                        count += 1
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                
    logger.info(f"Cleanup complete. Removed {count} items.")
    return {"removed_count": count}
