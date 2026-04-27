import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger(__name__)


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
    max_messages: int = int(os.getenv("MAX_MESSAGES", "10"))
    wait_time_seconds: int = int(os.getenv("WAIT_TIME_SECONDS", "1"))
    visibility_timeout: int = int(os.getenv("VISIBILITY_TIMEOUT", "30"))
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "postgres")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "password")
    db_schema: str = os.getenv("DB_SCHEMA", "secure_login")
    hash_secret: str = os.getenv("HASH_SECRET", "local-demo-secret")
    quarantine_invalid_events: bool = os.getenv("QUARANTINE_INVALID_EVENTS", "true").lower() == "true"


REQUIRED_FIELDS = {
    "user_id",
    "device_type",
    "device_id",
    "ip",
    "locale",
    "app_version",
}


def hash_value(raw_value: str) -> str:
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def hmac_value(raw_value: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_value.encode("utf-8"), hashlib.sha256).hexdigest()


def canonical_event_hash(event: dict[str, Any]) -> str:
    return hash_value(json.dumps(event, sort_keys=True, separators=(",", ":")))


def parse_major_version(app_version: str) -> int:
    major = app_version.split(".", 1)[0]
    return int(major)


def validate_event(event: dict[str, Any]) -> None:
    missing_fields = sorted(REQUIRED_FIELDS - set(event))
    if missing_fields:
        raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
    if not str(event["user_id"]).strip():
        raise ValueError("user_id cannot be blank")
    if str(event["device_type"]).lower() not in {"ios", "android", "web"}:
        raise ValueError("device_type must be one of ios, android, web")
    parse_major_version(str(event["app_version"]))


def transform_event(
    event: dict[str, Any],
    ingested_at: datetime | None = None,
    *,
    hash_secret: str = "local-demo-secret",
    batch_id: str | None = None,
) -> dict[str, Any]:
    validate_event(event)
    timestamp = ingested_at or datetime.now(timezone.utc)
    source_hash = canonical_event_hash(event)
    return {
        "event_id": hmac_value(source_hash, hash_secret),
        "batch_id": batch_id or "interactive",
        "user_id": str(event["user_id"]),
        "device_type": str(event["device_type"]).lower(),
        "masked_ip": hmac_value(str(event["ip"]), hash_secret),
        "masked_device_id": hmac_value(str(event["device_id"]), hash_secret),
        "locale": str(event["locale"]),
        "app_version": parse_major_version(str(event["app_version"])),
        "app_version_raw": str(event["app_version"]),
        "source_event_hash": source_hash,
        "pii_strategy": "hmac_sha256_secret_salted",
        "create_date": timestamp.date(),
        "ingested_at_utc": timestamp,
    }


def build_sqs_client(settings: Settings):
    import boto3

    return boto3.client(
        "sqs",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.sqs_endpoint_url,
        region_name=settings.aws_region,
    )


def fetch_messages(settings: Settings) -> list[dict[str, Any]]:
    sqs = build_sqs_client(settings)
    response = sqs.receive_message(
        QueueUrl=settings.sqs_queue_url,
        MaxNumberOfMessages=settings.max_messages,
        WaitTimeSeconds=settings.wait_time_seconds,
        VisibilityTimeout=settings.visibility_timeout,
        MessageAttributeNames=["All"],
    )
    return response.get("Messages", [])


def parse_messages(messages: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str]]:
    parsed_messages: list[tuple[dict[str, Any], str]] = []
    for message in messages:
        receipt_handle = message.get("ReceiptHandle")
        body = message.get("Body", "")
        if not receipt_handle:
            LOGGER.warning("Skipping message without receipt handle: %s", message)
            continue
        parsed_messages.append((json.loads(body), receipt_handle))
    return parsed_messages


def get_db_connection(settings: Settings):
    import psycopg

    return psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        dbname=settings.db_name,
    )


def ensure_table_exists(cursor, schema: str = "secure_login") -> None:
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.user_logins (
            event_id varchar(128) PRIMARY KEY,
            batch_id varchar(64) NOT NULL,
            user_id varchar(128) NOT NULL,
            device_type varchar(32) NOT NULL,
            masked_ip varchar(256) NOT NULL,
            masked_device_id varchar(256) NOT NULL,
            locale varchar(32) NOT NULL,
            app_version integer NOT NULL,
            app_version_raw varchar(64) NOT NULL,
            source_event_hash varchar(128) NOT NULL,
            pii_strategy varchar(64) NOT NULL,
            create_date date NOT NULL,
            ingested_at_utc timestamptz NOT NULL
        );
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.ingestion_audit (
            batch_id varchar(64) PRIMARY KEY,
            started_at_utc timestamptz NOT NULL,
            completed_at_utc timestamptz NOT NULL,
            messages_received integer NOT NULL,
            records_loaded integer NOT NULL,
            records_rejected integer NOT NULL
        );
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.quarantine_login_events (
            quarantine_id bigserial PRIMARY KEY,
            batch_id varchar(64) NOT NULL,
            rejected_at_utc timestamptz NOT NULL,
            error_message text NOT NULL,
            payload jsonb NOT NULL
        );
        """
    )


def insert_events(cursor, rows: list[dict[str, Any]], schema: str = "secure_login") -> None:
    cursor.executemany(
        f"""
        INSERT INTO {schema}.user_logins (
            event_id, batch_id, user_id, device_type, masked_ip, masked_device_id,
            locale, app_version, app_version_raw, source_event_hash, pii_strategy,
            create_date, ingested_at_utc
        ) VALUES (
            %(event_id)s, %(batch_id)s, %(user_id)s, %(device_type)s, %(masked_ip)s,
            %(masked_device_id)s, %(locale)s, %(app_version)s, %(app_version_raw)s,
            %(source_event_hash)s, %(pii_strategy)s, %(create_date)s, %(ingested_at_utc)s
        )
        ON CONFLICT (event_id) DO NOTHING
        """,
        rows,
    )


def insert_quarantine(cursor, batch_id: str, rejected_rows: list[dict[str, Any]], schema: str) -> None:
    if not rejected_rows:
        return
    cursor.executemany(
        f"""
        INSERT INTO {schema}.quarantine_login_events (
            batch_id, rejected_at_utc, error_message, payload
        ) VALUES (%(batch_id)s, %(rejected_at_utc)s, %(error_message)s, %(payload)s)
        """,
        rejected_rows,
    )


def insert_audit(
    cursor,
    *,
    schema: str,
    batch_id: str,
    started_at: datetime,
    completed_at: datetime,
    messages_received: int,
    records_loaded: int,
    records_rejected: int,
) -> None:
    cursor.execute(
        f"""
        INSERT INTO {schema}.ingestion_audit (
            batch_id, started_at_utc, completed_at_utc, messages_received,
            records_loaded, records_rejected
        ) VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (batch_id) DO NOTHING
        """,
        (batch_id, started_at, completed_at, messages_received, records_loaded, records_rejected),
    )


def delete_processed_messages(settings: Settings, receipt_handles: list[str]) -> None:
    if not receipt_handles:
        return

    sqs = build_sqs_client(settings)
    entries = [
        {"Id": str(index), "ReceiptHandle": receipt_handle}
        for index, receipt_handle in enumerate(receipt_handles)
    ]
    sqs.delete_message_batch(QueueUrl=settings.sqs_queue_url, Entries=entries)


def run() -> int:
    settings = Settings()
    batch_id = uuid4().hex
    started_at = datetime.now(timezone.utc)
    messages = fetch_messages(settings)
    if not messages:
        LOGGER.info("No messages available in queue %s", settings.sqs_queue_url)
        return 0

    parsed_messages = parse_messages(messages)
    transformed_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    processed_receipts: list[str] = []

    for event, receipt_handle in parsed_messages:
        try:
            transformed_rows.append(
                transform_event(event, hash_secret=settings.hash_secret, batch_id=batch_id)
            )
            processed_receipts.append(receipt_handle)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            LOGGER.warning("Quarantining invalid event: %s", exc)
            rejected_rows.append(
                {
                    "batch_id": batch_id,
                    "rejected_at_utc": datetime.now(timezone.utc),
                    "error_message": str(exc),
                    "payload": json.dumps(event),
                }
            )
            if settings.quarantine_invalid_events:
                processed_receipts.append(receipt_handle)

    if not transformed_rows and not rejected_rows:
        LOGGER.warning("No parsable events were found in %s messages", len(messages))
        return 1

    with get_db_connection(settings) as connection:
        with connection.cursor() as cursor:
            ensure_table_exists(cursor, settings.db_schema)
            insert_events(cursor, transformed_rows, settings.db_schema)
            insert_quarantine(cursor, batch_id, rejected_rows, settings.db_schema)
            insert_audit(
                cursor,
                schema=settings.db_schema,
                batch_id=batch_id,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                messages_received=len(messages),
                records_loaded=len(transformed_rows),
                records_rejected=len(rejected_rows),
            )
        connection.commit()

    delete_processed_messages(settings, processed_receipts)
    LOGGER.info(
        "Batch %s loaded=%s rejected=%s received=%s",
        batch_id,
        len(transformed_rows),
        len(rejected_rows),
        len(messages),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
