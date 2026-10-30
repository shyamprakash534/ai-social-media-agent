from celery import Celery
from app.config import settings

celery_app = Celery("ai_social_media_agent", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={"check-due-social-posts-every-minute": {"task": "app.tasks.dispatch_due_posts", "schedule": 60.0}},
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
