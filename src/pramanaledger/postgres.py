from datetime import datetime
from typing import Any

from pramanaledger.config import Settings


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
            event_time_utc varchar(64) NOT NULL,
            auth_result varchar(16) NOT NULL,
            risk_band varchar(16) NOT NULL,
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
            locale, event_time_utc, auth_result, risk_band, app_version, app_version_raw,
            source_event_hash, pii_strategy, create_date, ingested_at_utc
        ) VALUES (
            %(event_id)s, %(batch_id)s, %(user_id)s, %(device_type)s, %(masked_ip)s,
            %(masked_device_id)s, %(locale)s, %(event_time_utc)s, %(auth_result)s,
            %(risk_band)s, %(app_version)s, %(app_version_raw)s, %(source_event_hash)s,
            %(pii_strategy)s, %(create_date)s, %(ingested_at_utc)s
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
