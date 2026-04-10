"""Application configuration for the oligo backend."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded entirely from environment variables."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore',
    )

    APP_NAME: str = 'oligo-backend'
    ENVIRONMENT: str = 'local'
    LOG_LEVEL: str = 'INFO'
    API_HOST: str = '0.0.0.0'
    API_PORT: int = 8000
    API_DEFAULT_LIMIT: int = 50
    API_MAX_LIMIT: int = 200

    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_TOPIC_RUNTIME: str
    KAFKA_TOPIC_THREAT: str
    KAFKA_TOPIC_DLQ: str
    KAFKA_AUTO_OFFSET_RESET: str = 'latest'
    KAFKA_PRODUCER_RETRIES: int = 3
    CONSUMER_MAX_RETRIES: int = 3

    POSTGRES_DSN: str
    PGBOUNCER_DSN: str
    POSTGRES_POOL_MIN_SIZE: int = 5
    POSTGRES_POOL_MAX_SIZE: int = 20

    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_BLOOM_KEY: str = 'oligo:processed-events:bloom'
    JOIN_TTL_MS: int = Field(default=200, ge=50)
    PENDING_WRITE_DELAY_MS: int = Field(default=250, ge=100)

    SLACK_WEBHOOK_URL: str
    JIRA_BASE_URL: str
    JIRA_API_TOKEN: str
    ALERT_COOLDOWN_SECONDS: int = 900
    HTTP_TIMEOUT_SECONDS: float = 5.0

    AI_MODEL_SERVER_URL: str
    AI_INLINE_SCORE_TIMEOUT_MS: int = 10
