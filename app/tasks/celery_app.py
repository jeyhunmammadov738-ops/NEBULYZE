from celery import Celery
import os
from dotenv import load_dotenv

# Circuit breakers
from ..circuit_breakers import redis_breaker

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "nebulyze_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.worker", "app.tasks.backend_cleanup"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600, # 10 minutes max per task
)

# Celery Beat Schedule for cleanup
celery_app.conf.beat_schedule = {
    "aggressive-cleanup-every-30-mins": {
        "task": "app.tasks.backend_cleanup.auto_cleanup_task",
        "schedule": 1800.0, # Every 30 minutes
    },
}

