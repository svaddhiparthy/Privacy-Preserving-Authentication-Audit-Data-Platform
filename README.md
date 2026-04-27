# Privacy Preserving Authentication Audit Data Platform

Privacy Preserving Authentication Audit Data Platform is a local-first data engineering project for secure authentication-event ingestion. The platform consumes login-event messages from an SQS-compatible queue, validates the event contract, tokenizes sensitive fields with secret-keyed HMAC-SHA256, writes idempotent analytical records into PostgreSQL, quarantines malformed records, and records batch-level audit evidence.

The short internal product name is `PramanaLedger`.

The public route planned for the portfolio surface is:

```text
https://surya.vaddhiparthy.com/privacy-preserving-authentication-audit-data-platform
```

## Current Implementation

The current working implementation is intentionally compact and testable:

| Capability | Status | Implementation |
|---|---|---|
| SQS-compatible ingestion | Working locally | LocalStack SQS plus `pramanaledger.sqs` |
| Contract validation | Working | `pramanaledger.transform.validate_event` |
| PII tokenization | Working | HMAC-SHA256 in `pramanaledger.tokenization` |
| Deterministic event ID | Working | HMAC over canonical event hash |
| PostgreSQL curated table | Working | `secure_login.user_logins` |
| Quarantine table | Working | `secure_login.quarantine_login_events` |
| Batch audit table | Working | `secure_login.ingestion_audit` |
| Demo API | Working locally and deployed | `demo_api.py` |
| Public technical surface | Working | Platform summary, flow, transform preview, data browser, schema, contract, controls, and knowledge bank |
| Unit tests | Working | `tests/test_code_fetch_vaddhiparthy.py` |

## Architecture

```text
Login Events JSON
        |
        v
LocalStack SQS
        |
        v
Ingestion Worker
        |
        +--> validate event contract
        +--> reject malformed events to quarantine
        +--> tokenize IP and device identifiers
        +--> generate deterministic event_id
        |
        v
PostgreSQL secure_login schema
        |
        +--> user_logins
        +--> quarantine_login_events
        +--> ingestion_audit
```

The platform uses deterministic idempotency rather than source-provided identifiers. The `event_id` is derived from a canonical source-event hash and a secret HMAC key. Replaying the same event produces the same key, and PostgreSQL enforces `ON CONFLICT DO NOTHING` at the storage boundary.

## Package Layout

```text
src/pramanaledger/
  config.py        # environment-backed runtime settings
  tokenization.py  # hash and HMAC helpers
  transform.py     # validation and event transformation
  sqs.py           # SQS receive/delete helpers
  postgres.py      # schema creation and persistence functions
  runner.py        # batch orchestration

code_fetch_vaddhiparthy.py  # compatibility entrypoint
demo_api.py                 # local FastAPI demo service
sql/                        # database schema
docs/                       # architecture and wiki-ready documentation
tests/                      # unit tests
```

## Data Contract

Each login event must include:

| Field | Description |
|---|---|
| `user_id` | Logical user identifier |
| `device_type` | One of `ios`, `android`, or `web` |
| `device_id` | Raw device identifier, tokenized before persistence |
| `ip` | Raw IP address, tokenized before persistence |
| `locale` | Locale string such as `en_US` |
| `app_version` | Semantic application version; major version is extracted |
| `event_time_utc` | Optional event timestamp used for preview and future warehouse partitioning |
| `auth_result` | Optional authentication outcome, `success` or `failure` |
| `risk_band` | Optional operational risk band, `low`, `medium`, or `high` |

Malformed events are rejected into quarantine with the original payload and error message. They are not silently coerced into placeholder values.

The current JSON Schema contract is stored at:

```text
contracts/v1/login_event.schema.json
```

## Database Model

Target schema:

```text
secure_login
```

Tables:

| Table | Purpose |
|---|---|
| `secure_login.user_logins` | Curated login-event records with tokenized sensitive fields |
| `secure_login.quarantine_login_events` | Rejected payloads and validation reasons |
| `secure_login.ingestion_audit` | Batch start/end timestamps, received count, loaded count, rejected count |

View:

| View | Purpose |
|---|---|
| `secure_login.vw_ingestion_health` | Latest completed load, total loaded records, total rejected records, batch count |

## Local Development

Start local infrastructure:

```powershell
docker compose up -d
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create the LocalStack queue:

```powershell
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name login-queue
```

Send a sample event:

```powershell
aws --endpoint-url=http://localhost:4566 sqs send-message `
  --queue-url http://localhost:4566/000000000000/login-queue `
  --message-body '{\"user_id\":\"user_123\",\"device_type\":\"android\",\"device_id\":\"A1B2C3D4\",\"ip\":\"192.168.1.10\",\"locale\":\"en_US\",\"app_version\":\"5.2.3\"}'
```

Run the ingestion worker:

```powershell
python code_fetch_vaddhiparthy.py
```

Run the demo API:

```powershell
uvicorn demo_api:app --reload --port 8075
```

Open:

```text
http://127.0.0.1:8075
```

## Configuration

Configuration is environment-driven. Use `.env.example` as the template and keep real values in ignored `.env` files.

| Variable | Purpose |
|---|---|
| `SQS_ENDPOINT_URL` | LocalStack or AWS SQS endpoint |
| `SQS_QUEUE_URL` | Login-event queue URL |
| `MAX_MESSAGES` | Batch receive size |
| `WAIT_TIME_SECONDS` | SQS long-poll wait time |
| `VISIBILITY_TIMEOUT` | SQS visibility timeout |
| `DB_HOST` | PostgreSQL host |
| `DB_PORT` | PostgreSQL port |
| `DB_NAME` | PostgreSQL database |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_SCHEMA` | Target schema, default `secure_login` |
| `HASH_SECRET` | Secret used for deterministic HMAC tokenization |
| `QUARANTINE_INVALID_EVENTS` | Whether rejected messages are deleted from the queue after quarantine |

No real secret values belong in committed code, markdown, SQL, logs, or Docker build context.

## Validation

Run unit tests:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Compile the Python modules:

```powershell
Get-ChildItem src\pramanaledger\*.py | ForEach-Object { python -m py_compile $_.FullName }
python -m py_compile code_fetch_vaddhiparthy.py demo_api.py
```

Run the smoke script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
```

## Planned Expansion

The next implementation target is to expand this into a full technical portfolio system using the same operating style as the completed FinLens platform:

1. PII vault with controlled re-identification and access audit.
2. Versioned source contracts under `contracts/`.
3. Bronze, Silver, and Gold data layers.
4. dbt models and privacy-focused tests.
5. Airflow orchestration.
6. Technical control room with pipeline status, quality status, table browser, and transformation previews.
7. Wiki-style knowledge bank.
8. Public portfolio route at the planned slug.

The system will remain local-first. Real cloud services are optional and should only be enabled after the local path is working and tested.

## Public Surface Contents

The deployed page is a technical surface, not only a landing page. It currently exposes:

| Section | Backing asset |
|---|---|
| Platform overview | `demo_api.platform_summary` |
| Data flow | `demo_api.flow` |
| Live transform preview | `sample_data/login_events.jsonl` plus `pramanaledger.transform` |
| Data table browser | `demo_api.table_preview` |
| PostgreSQL schema viewer | `sql/001_secure_login_schema.sql` |
| Source contract viewer | `contracts/v1/login_event.schema.json` |
| Quality and privacy gates | `demo_api.quality_gates` |
| Knowledge bank | `docs/wiki/pramanaledger_knowledge_bank.md` |

The sample dataset is deterministic synthetic authentication telemetry. It is intentionally generated rather than scraped from public user activity because authentication logs are sensitive by nature and public samples are often licensed, stale, or stripped of useful operational fields.
