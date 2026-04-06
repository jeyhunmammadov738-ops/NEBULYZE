from .celery_app import celery_app
from ..core.engine import convert_to_mp3, convert_to_voice
import os
import logging
from typing import Optional, Tuple

# Circuit breakers
from ..circuit_breakers import redis_breaker, external_api_breaker

logger = logging.getLogger(__name__)

class ConversionError(Exception):
    """Custom exception for conversion errors"""
    pass

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def convert_media_task(self, input_path: str, output_path: str, bitrate: str = "192k", fmt: str = "mp3", trim: Optional[Tuple[float, float]] = None):
    """
    Background task for media conversion.
    Updates progress state for frontend/bot to poll.
    """
    logger.info(f"Starting conversion task: {input_path} -> {output_path}")
    self.update_state(state="PROGRESS", meta={"status": "Initializing conversion engine..."})
    
    # Validate input file exists
    if not os.path.exists(input_path):
        error_msg = f"Input file not found: {input_path}"
        logger.error(error_msg)
        self.update_state(state="FAILURE", meta={"status": error_msg})
        raise ConversionError(error_msg)
    
    try:
        self.update_state(state="PROGRESS", meta={"status": "Starting conversion..."})
        
        if fmt == "mp3":
            convert_to_mp3(input_path, output_path, bitrate, trim)
        else:
            convert_to_voice(input_path, output_path, trim)
            
        # Verify output file was created
        if not os.path.exists(output_path):
            error_msg = "Conversion completed but output file not found"
            logger.error(error_msg)
            self.update_state(state="FAILURE", meta={"status": error_msg})
            raise ConversionError(error_msg)
            
        # Aggressive cleanup: remove input file after successful conversion
        if os.path.exists(input_path):
            os.remove(input_path)
            logger.info(f"Cleaned up input file: {input_path}")
            
        success_msg = "Conversion complete!"
        logger.info(success_msg)
        self.update_state(state="SUCCESS", meta={"status": success_msg, "output_path": output_path})
        return {"status": "SUCCESS", "output_path": output_path}
        
    except ConversionError as e:
        logger.error(f"Conversion failed: {e}")
        # Even if it fails, we might want to clean up the input if it's in temp_uploads
        if "temp_uploads" in input_path and os.path.exists(input_path):
            os.remove(input_path)
        self.update_state(state="FAILURE", meta={"status": str(e)})
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during conversion: {e}")
        # Even if it fails, we might want to clean up the input if it's in temp_uploads
        if "temp_uploads" in input_path and os.path.exists(input_path):
            os.remove(input_path)
        self.update_state(state="FAILURE", meta={"status": f"Unexpected error: {str(e)}"})
        # Retry on transient errors
        raise self.retry(exc=e, countdown=60)
