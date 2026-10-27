from collections import Counter
from datetime import UTC, datetime, timedelta

TERMINAL_QUERY_STATUSES = frozenset({"succeeded", "failed"})


def derive_job_status(query_statuses: list[str], *, started: bool) -> str:
    if not query_statuses:
        return "pending"
    counts = Counter(query_statuses)
    total = len(query_statuses)
    if counts["succeeded"] == total:
        return "completed"
    if counts["failed"] == total:
        return "failed"
    if counts["succeeded"] + counts["failed"] == total:
        return "partial_failed"
    return "running" if started else "pending"


def retry_at(*, attempt_count: int, base_seconds: int, now: datetime | None = None) -> datetime:
    current_time = now or datetime.now(UTC)
    delay = min(base_seconds * (2 ** max(attempt_count - 1, 0)), base_seconds * 4)
    deterministic_jitter = attempt_count % 11
    return current_time + timedelta(seconds=delay + deterministic_jitter)
