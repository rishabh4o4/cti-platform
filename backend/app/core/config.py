from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_VALUES = {"change-me", "minioadmin", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Threat Intelligence API"
    environment: str = "local"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] | str = Field(default_factory=lambda: ["http://localhost:3000"])

    database_url: str = "postgresql+asyncpg://police:police@localhost:5432/police"
    database_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"
    neo4j_max_pool_size: int = 10

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "evidence"

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    admin_username: str = "admin"
    admin_password: str = "change-me"
    internal_api_keys: list[str] = Field(default_factory=list)

    risk_threshold_high: float = 50.0
    risk_threshold_critical: float = 75.0
    alert_webhook_url: str | None = None
    intelligence_confidence_threshold: float = 0.5
    ws_max_connections: int = 50
    alert_cooldown_seconds_high: int = 300
    alert_cooldown_seconds_critical: int = 60

    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None
    reddit_subreddits: list[str] = Field(default_factory=list)
    reddit_poll_interval_minutes: int = 15
    reddit_fetch_limit: int = 50
    # Max comments collected per post; effective item ceiling = fetch_limit × (1 + comment_limit)
    reddit_comment_limit: int = 10

    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_session_string: str | None = None
    telegram_channels: list[str] = Field(default_factory=list)
    telegram_poll_interval_minutes: int = 15
    telegram_fetch_limit: int = 50

    max_bfs_depth: int = 3
    graph_new_channels_per_cycle: int = 5

    x_accounts: list[str] = Field(default_factory=list)
    x_poll_interval_minutes: int = 15
    x_fetch_limit: int = 50

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("cors_origins", mode="after")
    @classmethod
    def validate_cors_origins(cls, value: list[str], info: Any) -> list[str]:
        environment = info.data.get("environment", "local")
        if environment == "production":
            for origin in value:
                if "localhost" in origin or "127.0.0.1" in origin:
                    raise ValueError(f"Localhost origin not allowed in production: {origin}")
        return value

    @field_validator("internal_api_keys", mode="before")
    @classmethod
    def parse_internal_api_keys(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [key.strip() for key in value.split(",") if key.strip()]
        return value

    @field_validator("reddit_subreddits", mode="before")
    @classmethod
    def parse_reddit_subreddits(cls, value: Any) -> list[str]:
        # Return [] when the env var is absent/empty — RedditCollector handles it gracefully.
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [sub.strip() for sub in value.split(",") if sub.strip()]
        return value

    @field_validator("telegram_channels", mode="before")
    @classmethod
    def parse_telegram_channels(cls, value: Any) -> list[str]:
        # Return [] when the env var is absent/empty — TelegramCollector handles it gracefully.
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [ch.strip() for ch in value.split(",") if ch.strip()]
        return value

    @field_validator("x_accounts", mode="before")
    @classmethod
    def parse_x_accounts(cls, value: Any) -> list[str]:
        # Return [] when the env var is absent/empty — XCollector handles it gracefully.
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [acc.strip().lower() for acc in value.split(",") if acc.strip()]
        if isinstance(value, list):
            return [acc.strip().lower() for acc in value if isinstance(acc, str) and acc.strip()]
        return value

    @field_validator("jwt_secret_key", mode="after")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if v in _PLACEHOLDER_VALUES:
            raise ValueError(
                "JWT_SECRET_KEY must be set to a long random secret; "
                "the default placeholder is not safe for any environment."
            )
        return v

    @field_validator("admin_password", mode="after")
    @classmethod
    def validate_admin_password(cls, v: str) -> str:
        if v in _PLACEHOLDER_VALUES:
            raise ValueError(
                "ADMIN_PASSWORD must be changed from the default placeholder."
            )
        return v

    @field_validator("minio_secret_key", mode="after")
    @classmethod
    def validate_minio_secret(cls, v: str) -> str:
        if v in _PLACEHOLDER_VALUES:
            raise ValueError(
                "MINIO_SECRET_KEY must be changed from the default 'minioadmin' credential."
            )
        return v

    @property
    def celery_broker(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def celery_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
