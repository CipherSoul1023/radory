from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.router import router
from app.core.config import get_settings
from app.core.monitoring import configure_sentry

settings = get_settings()
configure_sentry(settings)

app = FastAPI(title="Radory API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(auth_router)
