from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    app_name: str = "OsuRender API"
    app_version: str = "1.0.0"
    debug: bool = False
    database_url: str = Field(default="postgresql+asyncpg://osurender:osurender@localhost:5432/osurender")
    database_url_sync: str = Field(default="postgresql+psycopg2://osurender:osurender@localhost:5432/osurender")
    redis_url: str = Field(default="redis://localhost:6379/0")
    storage_endpoint: str = Field(default="localhost:9000")
    storage_access_key: str = Field(default="minioadmin")
    storage_secret_key: str = Field(default="minioadmin")
    storage_bucket_name: str = Field(default="osurender")
    storage_use_ssl: bool = Field(default=False)
    osu_api_key: str = Field(default="")
    default_skin: str = "Default"
    default_bg_dim: float = 0.95
    default_resolution: str = "1080p"
    render_timeout_seconds: int = 600
    max_replay_size_mb: int = 50
    max_skin_size_mb: int = 200
    cors_origins: list[str] = ["*"]
@lru_cache()
def get_settings() -> Settings:
    return Settings()