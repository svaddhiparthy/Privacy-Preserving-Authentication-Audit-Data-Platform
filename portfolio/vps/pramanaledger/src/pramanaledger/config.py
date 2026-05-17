import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "test")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    sqs_endpoint_url: str = os.getenv("SQS_ENDPOINT_URL", "http://localhost:4566")
    sqs_queue_url: str = os.getenv(
        "SQS_QUEUE_URL",
        "http://localhost:4566/000000000000/login-queue",
    )
    max_messages: int = _env_int("MAX_MESSAGES", 10)
    wait_time_seconds: int = _env_int("WAIT_TIME_SECONDS", 1)
    visibility_timeout: int = _env_int("VISIBILITY_TIMEOUT", 30)
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = _env_int("DB_PORT", 5432)
    db_name: str = os.getenv("DB_NAME", "postgres")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "password")
    db_schema: str = os.getenv("DB_SCHEMA", "secure_login")
    hash_secret: str = os.getenv("HASH_SECRET", "local-demo-secret")
    quarantine_invalid_events: bool = _env_bool("QUARANTINE_INVALID_EVENTS", True)
