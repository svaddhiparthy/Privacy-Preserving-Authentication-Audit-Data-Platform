# Secure Login Events Ingestion

Python data engineering project that consumes login events from AWS SQS via LocalStack, validates event contracts, tokenizes sensitive fields with HMAC-SHA256, quarantines malformed events, writes idempotent analytics-ready records into PostgreSQL, and records batch audit evidence.

## Why This Project Matters

This project demonstrates common data engineering concerns in a compact pipeline:

- event ingestion from a queue
- PII tokenization before persistence
- schema-aware transformation
- quarantine handling for bad records
- idempotent writes through deterministic event IDs
- batch-level audit metadata
- local reproducibility with Docker
- testable business logic

It is a good starter project for discussing secure ingestion, operational reliability, and how to evolve a batch script into a production-grade pipeline.

## Architecture

```text
Login Events JSON
        |
        v
   LocalStack SQS
        |
        v
 Python ETL Pipeline
   - extract messages
   - validate required fields
   - hash IP and device_id
   - parse major app version
        |
        v
   PostgreSQL schema
     secure_login.user_logins
     secure_login.quarantine_login_events
     secure_login.ingestion_audit
```

## Project Structure

```text
.
|-- code_fetch_vaddhiparthy.py
|-- docker-compose.yml
|-- requirements.txt
|-- sample_data/
|   `-- login_events.jsonl
`-- tests/
    `-- test_code_fetch_vaddhiparthy.py
```

## Data Model

Target table: `user_logins`

| Column | Type | Description |
|---|---|---|
| `event_id` | `varchar(128)` | Deterministic idempotency key |
| `batch_id` | `varchar(64)` | Ingestion batch identifier |
| `user_id` | `varchar(128)` | Logical user identifier |
| `device_type` | `varchar(32)` | Device family such as `ios` or `android` |
| `masked_ip` | `varchar(256)` | HMAC-SHA256 token of the original IP |
| `masked_device_id` | `varchar(256)` | HMAC-SHA256 token of the original device ID |
| `locale` | `varchar(32)` | Locale such as `en_US` |
| `app_version` | `integer` | Major app version extracted from semantic version |
| `create_date` | `date` | Ingestion date |
| `ingested_at_utc` | `timestamptz` | Load timestamp |

## Local Run

1. Start infrastructure:

   ```bash
   docker compose up -d
   ```

2. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create the queue in LocalStack:

   ```bash
   aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name login-queue
   ```

4. Send a sample event:

   ```bash
   aws --endpoint-url=http://localhost:4566 sqs send-message \
     --queue-url http://localhost:4566/000000000000/login-queue \
     --message-body "{\"user_id\":\"user_123\",\"device_type\":\"android\",\"device_id\":\"A1B2C3D4\",\"ip\":\"192.168.1.10\",\"locale\":\"en_US\",\"app_version\":\"5.2.3\"}"
   ```

5. Run the ETL:

   ```bash
python code_fetch_vaddhiparthy.py
```

## Demo Website

Run the local project demo:

```bash
uvicorn demo_api:app --reload --port 8075
```

Open `http://127.0.0.1:8075`.

## Configuration

Runtime settings are controlled with environment variables. Defaults are provided in `.env.example`.

- `SQS_ENDPOINT_URL`
- `SQS_QUEUE_URL`
- `MAX_MESSAGES`
- `WAIT_TIME_SECONDS`
- `VISIBILITY_TIMEOUT`
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

## Tests

Run the unit tests with:

```bash
python -m unittest discover -s tests -p "test_*.py"
```
