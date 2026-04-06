import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    """
    Set up logging configuration for the application.
    """
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(),  # Log to console
            RotatingFileHandler(
                os.path.join(log_dir, "app.log"),
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
        ]
    )
    
    # Set higher level for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)

def get_logger(name: str):
    """
    Get a logger with the specified name.
    """
    return logging.getLogger(name)