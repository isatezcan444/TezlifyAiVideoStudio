import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

class Settings(BaseSettings):
    app_name: str = Field(default="Tezlify YouTube Creator Studio", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    host: str = Field(default="127.0.0.1", alias="HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    frontend_port: int = Field(default=5173, alias="FRONTEND_PORT")

    data_dir: str = Field(default="./data", alias="DATA_DIR")
    max_upload_size_mb: int = Field(default=500, alias="MAX_UPLOAD_SIZE_MB")
    allowed_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="ALLOWED_ORIGINS"
    )

    # Google / YouTube OAuth
    google_client_id: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    youtube_client_id: Optional[str] = Field(default=None, alias="YOUTUBE_CLIENT_ID")
    youtube_client_secret: Optional[str] = Field(default=None, alias="YOUTUBE_CLIENT_SECRET")
    youtube_redirect_uri: str = Field(
        default="http://127.0.0.1:8000/api/v1/social/youtube/callback",
        alias="YOUTUBE_REDIRECT_URI"
    )

    # Scheduler Settings
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    scheduler_interval_seconds: int = Field(default=30, alias="SCHEDULER_INTERVAL_SECONDS")
    scheduler_missed_grace_period_minutes: int = Field(default=60, alias="SCHEDULER_MISSED_GRACE_PERIOD_MINUTES")
    scheduler_max_attempts: int = Field(default=3, alias="SCHEDULER_MAX_ATTEMPTS")
    scheduler_retry_delay_minutes: int = Field(default=5, alias="SCHEDULER_RETRY_DELAY_MINUTES")

    # YouTube Analytics query guardrails
    analytics_max_range_days: int = Field(default=365, alias="ANALYTICS_MAX_RANGE_DAYS")
    analytics_default_range_days: int = Field(default=28, alias="ANALYTICS_DEFAULT_RANGE_DAYS")

    model_config = SettingsConfigDict(
        env_file=os.path.join(PROJECT_ROOT, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def resolved_data_dir(self) -> str:
        if os.path.isabs(self.data_dir):
            return self.data_dir
        return os.path.abspath(os.path.join(PROJECT_ROOT, self.data_dir))

    @property
    def database_url(self) -> str:
        db_path = os.path.join(self.resolved_data_dir, "database", "tezlify_studio.db")
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        return f"sqlite:///{os.path.abspath(db_path)}"

    @property
    def media_dir(self) -> str:
        path = os.path.join(self.resolved_data_dir, "media")
        os.makedirs(os.path.abspath(path), exist_ok=True)
        return os.path.abspath(path)

    @property
    def temp_dir(self) -> str:
        path = os.path.join(self.resolved_data_dir, "temp")
        os.makedirs(os.path.abspath(path), exist_ok=True)
        return os.path.abspath(path)

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def resolved_youtube_client_id(self) -> Optional[str]:
        return self.youtube_client_id or self.google_client_id

    @property
    def resolved_youtube_client_secret(self) -> Optional[str]:
        return self.youtube_client_secret or self.google_client_secret

settings = Settings()
