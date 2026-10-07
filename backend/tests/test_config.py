from app.core.config import Settings


def test_neon_postgres_url_uses_installed_driver():
    settings = Settings(database_url="postgresql://host/db")
    assert settings.database_url == "postgresql+psycopg://host/db"
