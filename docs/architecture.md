# Secure Login Events Ingestion Architecture

## Executive Summary

This project is now positioned as a secure event ingestion platform rather than a single Python ETL script. It demonstrates queue consumption, contract validation, PII tokenization, idempotent analytics loading, quarantine handling, and operational audit trails.

## Data Flow

1. Login events arrive in SQS.
2. The ingestion worker receives a bounded batch.
3. Raw event shape is validated against required contract fields.
4. Direct identifiers are replaced with HMAC-SHA256 tokens.
5. Valid events are loaded into `secure_login.user_logins`.
6. Invalid events are loaded into `secure_login.quarantine_login_events`.
7. Batch metadata is written to `secure_login.ingestion_audit`.

## Data Engineering Signals

- Idempotency through deterministic `event_id`.
- PII minimization before durable persistence.
- Quarantine path for malformed records.
- Audit table for SLA, freshness, and recovery discussions.
- LocalStack and Postgres Docker services for reproducible local execution.
- Demo API for web presentation and recruiter walkthroughs.

## Enterprise-Grade Additions To Implement Next

- **dbt** for bronze/silver/gold models and data tests.
- **Great Expectations** for field-level validation reports and quality gates.
- **Airflow or Dagster** for orchestration, retries, backfills, and dependency visualization.
- **OpenLineage-compatible event model** for job, run, and dataset lineage.
- **Prometheus and Grafana** for ingestion lag, reject rate, queue depth, and freshness SLA dashboards.
- **Kafka-compatible streaming mode** for high-throughput event ingestion.
- **Secrets-backed tokenization salt** through environment or vault integration.
- **Synthetic load generator** to demonstrate throughput and failure recovery.

## Future Production Hardening

- Add schema registry or event contract versioning.
- Add dbt models/tests over the curated tables.
- Add OpenLineage emission for job-level lineage.
- Add Prometheus counters and freshness alerts.
- Add partitioning by `create_date` for larger-scale workloads.
