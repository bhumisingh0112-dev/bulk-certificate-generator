from pathlib import Path
import os


class Settings:
    """Small environment-based settings object to keep local setup simple."""

    app_name: str = os.getenv("APP_NAME", "Bulk Certificate Generator API")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./certificate_jobs.db")
    storage_dir: Path = Path(os.getenv("STORAGE_DIR", "./generated"))


settings = Settings()
