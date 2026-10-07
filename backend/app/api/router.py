from fastapi import APIRouter, HTTPException
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.redis import get_redis
from app.database.session import get_engine
from app.workers.celery_app import celery_app
from app.workers.tasks import health_check_task

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness() -> dict[str, str]:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        get_redis().ping()
    except (SQLAlchemyError, RedisError) as exc:
        raise HTTPException(status_code=503, detail="Infrastructure unavailable") from exc
    return {"status": "ok"}


@router.post("/health/tasks")
def enqueue_health_task() -> dict[str, str]:
    if get_settings().app_env != "development":
        raise HTTPException(status_code=404)
    task = health_check_task.delay()
    return {"task_id": task.id}


@router.get("/health/tasks/{task_id}")
def health_task_result(task_id: str) -> dict[str, str]:
    if get_settings().app_env != "development":
        raise HTTPException(status_code=404)
    result = celery_app.AsyncResult(task_id)
    return {"status": result.status, "result": str(result.result) if result.successful() else ""}
