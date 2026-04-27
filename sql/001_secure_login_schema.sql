CREATE SCHEMA IF NOT EXISTS secure_login;

CREATE TABLE IF NOT EXISTS secure_login.user_logins (
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

CREATE TABLE IF NOT EXISTS secure_login.quarantine_login_events (
    quarantine_id bigserial PRIMARY KEY,
    batch_id varchar(64) NOT NULL,
    rejected_at_utc timestamptz NOT NULL,
    error_message text NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS secure_login.ingestion_audit (
    batch_id varchar(64) PRIMARY KEY,
    started_at_utc timestamptz NOT NULL,
    completed_at_utc timestamptz NOT NULL,
    messages_received integer NOT NULL,
    records_loaded integer NOT NULL,
    records_rejected integer NOT NULL
);

CREATE OR REPLACE VIEW secure_login.vw_ingestion_health AS
SELECT
    max(completed_at_utc) AS last_completed_at_utc,
    sum(records_loaded) AS total_records_loaded,
    sum(records_rejected) AS total_records_rejected,
    count(*) AS batch_count
FROM secure_login.ingestion_audit;
