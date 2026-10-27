import inspect

from app.tasks.radar_search import execute_search_query_task
from app.workers.celery_app import celery_app


def test_radar_tasks_are_registered_and_ignore_results():
    celery_app.loader.import_default_modules()
    assert "radory.radar.execute_search_query" in celery_app.tasks
    assert "radory.radar.reconcile_search_queries" in celery_app.tasks
    assert execute_search_query_task.ignore_result is True


def test_query_task_accepts_only_the_persisted_query_identifier():
    assert list(inspect.signature(execute_search_query_task.run).parameters) == ["search_query_id"]


def test_reconciler_is_scheduled_by_celery_beat():
    schedule = celery_app.conf.beat_schedule["reconcile-radar-search-queries"]
    assert schedule["task"] == "radory.radar.reconcile_search_queries"
