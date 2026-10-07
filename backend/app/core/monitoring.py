import sentry_sdk
from posthog import Posthog

from app.core.config import Settings


def configure_sentry(settings: Settings) -> None:
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env)


def create_posthog_client(settings: Settings) -> Posthog | None:
    if not settings.posthog_api_key:
        return None
    return Posthog(project_api_key=settings.posthog_api_key, host=settings.posthog_host)
