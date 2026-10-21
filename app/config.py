"""
StyleVision Backend — Application Settings
Loaded from environment variables / .env file via pydantic-settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_name: str = "StyleVision"
    debug: bool = True

    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "stylevision"

    # JWT Authentication
    jwt_secret_key: str = "CHANGE_THIS_BEFORE_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # File storage
    upload_dir: str = "uploads"
    catalogue_dir: str = "catalogue"
    max_upload_size: int = 10 * 1024 * 1024  # 10 MB
    allowed_extensions: str = "jpg,jpeg,png,webp"

    # CORS
    cors_origins: str = "http://localhost:8081,http://localhost:19006,exp://localhost:8081"

    # AI / Model mode
    tryon_mode: str = "prototype"  # "prototype" | "replicate" | "catvton"
    catvton_endpoint: str = ""
    replicate_api_token: str = ""
    cutout_api_key: str = ""

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once at startup)."""
    return Settings()
