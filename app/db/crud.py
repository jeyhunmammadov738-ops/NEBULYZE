from .database import async_session
from .models import ConversionStats
import logging

# Circuit breakers
from ..circuit_breakers import db_breaker

logger = logging.getLogger(__name__)

@db_breaker
async def log_conversion_stat(
    user_id: int, 
    file_size: int, 
    duration: float, 
    processing_time: float, 
    platform: str,
    success: bool = True, 
    error_message: str = None
):
    async with async_session() as session:
        stat = ConversionStats(
            user_id=user_id,
            file_size=file_size,
            duration=duration,
            processing_time=processing_time,
            platform=platform,
            success=success,
            error_message=error_message
        )
        session.add(stat)
        await session.commit()
        logger.info(f"Logged conversion stat: {platform} - Success: {success}")
