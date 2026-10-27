from ssl import CERT_REQUIRED

from celery import Celery

from app.core.config import get_settings
from app.core.monitoring import configure_sentry

settings = get_settings()
configure_sentry(settings)

celery_app = Celery(
    "radory",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks", "app.tasks.radar_search"],
)
celery_app.conf.update(task_ignore_result=False, result_expires=3600)
celery_app.conf.beat_schedule = {
    "reconcile-radar-search-queries": {
        "task": "radory.radar.reconcile_search_queries",
        "schedule": settings.radar_reconcile_interval_seconds,
    }
}
if settings.redis_url.startswith("rediss://"):
    ssl_options = {"ssl_cert_reqs": CERT_REQUIRED}
    celery_app.conf.broker_use_ssl = ssl_options
    celery_app.conf.redis_backend_use_ssl = ssl_options
