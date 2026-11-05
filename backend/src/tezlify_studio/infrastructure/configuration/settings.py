import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

class Settings(BaseSettings):
    app_name: str = Field(default="Tezlify AI Video Studio", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    host: str = Field(default="127.0.0.1", alias="HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    frontend_port: int = Field(default=5173, alias="FRONTEND_PORT")

    data_dir: str = Field(default="./data", alias="DATA_DIR")
    studio_projects_dir: str = Field(default="", alias="STUDIO_PROJECTS_DIR")
    studio_assets_dir: str = Field(default="", alias="STUDIO_ASSETS_DIR")
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

    # ElevenLabs AI Voice Integration (Aşama 4.4)
    elevenlabs_api_key: Optional[str] = Field(default=None, alias="ELEVENLABS_API_KEY")
    elevenlabs_default_model: str = Field(default="eleven_multilingual_v2", alias="ELEVENLABS_DEFAULT_MODEL")
    elevenlabs_api_base: str = Field(default="https://api.elevenlabs.io/v1", alias="ELEVENLABS_API_BASE")

    # Phoneme / viseme lip sync (Aşama 5.4)
    lip_sync_enabled: bool = Field(default=True, alias="LIP_SYNC_ENABLED")
    alignment_venv_dir: str = Field(default="./tools/alignment-venv", alias="ALIGNMENT_VENV_DIR")
    alignment_model_id: str = Field(
        default="Baybars/wav2vec2-xls-r-300m-cv8-turkish",
        alias="ALIGNMENT_MODEL_ID",
    )
    alignment_timeout_seconds: int = Field(default=600, alias="ALIGNMENT_TIMEOUT_SECONDS")

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
    def resolved_studio_projects_dir(self) -> str:
        """Render output tree. Absolute override, otherwise under DATA_DIR.

        This used to be `os.path.abspath("data/studio_projects")`, i.e. relative to
        whatever the process happened to be started from, so a test run with
        DATA_DIR pointing at a scratch tree still wrote into the user's real
        renders. Deriving it here makes DATA_DIR the single isolation switch.
        """
        if self.studio_projects_dir and os.path.isabs(self.studio_projects_dir):
            return self.studio_projects_dir
        path = os.path.join(self.resolved_data_dir, "studio_projects")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def resolved_studio_assets_dir(self) -> str:
        """Character/prop/background .blend tree, same isolation rule as above."""
        if self.studio_assets_dir and os.path.isabs(self.studio_assets_dir):
            return self.studio_assets_dir
        path = os.path.join(self.resolved_data_dir, "studio_assets")
        os.makedirs(path, exist_ok=True)
        return path

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

    @property
    def is_elevenlabs_configured(self) -> bool:
        return bool(self.elevenlabs_api_key and self.elevenlabs_api_key.strip())

    @property
    def audio_cache_dir(self) -> str:
        path = os.path.join(self.resolved_data_dir, "audio_cache")
        os.makedirs(os.path.abspath(path), exist_ok=True)
        return os.path.abspath(path)

    @property
    def resolved_alignment_venv_dir(self) -> str:
        if os.path.isabs(self.alignment_venv_dir):
            return self.alignment_venv_dir
        return os.path.abspath(os.path.join(PROJECT_ROOT, self.alignment_venv_dir))

    @property
    def alignment_python_executable(self) -> str:
        """Interpreter of the isolated alignment environment, if it exists.

        The application venv is Python 3.14 with no ML stack; torch and
        transformers live only in this separate environment and are reached by
        subprocess.
        """
        candidate = os.path.join(self.resolved_alignment_venv_dir, "bin", "python")
        return candidate if os.path.isfile(candidate) else ""

    @property
    def alignment_cache_dir(self) -> str:
        path = os.path.join(self.resolved_data_dir, "alignment_cache")
        os.makedirs(os.path.abspath(path), exist_ok=True)
        return os.path.abspath(path)

    @property
    def alignment_model_cache_dir(self) -> str:
        """HuggingFace cache kept inside the repo tree so no model lands in $HOME."""
        path = os.path.join(PROJECT_ROOT, "tools", "hf-cache")
        os.makedirs(os.path.abspath(path), exist_ok=True)
        return os.path.abspath(path)

settings = Settings()
