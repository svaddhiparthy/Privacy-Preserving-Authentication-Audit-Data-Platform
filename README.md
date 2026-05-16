# Privacy-Preserving Authentication Audit Pipeline

This repository implements a local-first authentication-event ingestion pipeline with privacy controls, replay-safe identity, quarantine handling, and batch audit evidence.

Public presentation: <https://surya.vaddhiparthy.com/privacy-preserving-authentication-audit-data-platform/>

## Implemented System

| Capability | Implementation |
| --- | --- |
| Queue intake | SQS-compatible ingestion with LocalStack support |
| Event contract | Required field, device type, auth result, risk band, and app-version validation |
| PII handling | Secret-keyed HMAC-SHA256 tokenization for IP and device identifiers |
| Replay safety | Deterministic `event_id` derived from canonical event hash |
| Curated storage | PostgreSQL `secure_login.user_logins` table |
| Quarantine | Rejected payloads and validation reasons in `secure_login.quarantine_login_events` |
| Audit evidence | Batch-level received, loaded, rejected, started, and completed counts |
| Demo/API surface | FastAPI endpoints for health, flow, contract, transform preview, and table preview |
| External dataset adapter | DAS Group RBA login dataset adapter for local offline runs |

## Architecture

```text
Login event JSON
  -> SQS-compatible queue
  -> batch ingestion worker
  -> contract validation
  -> HMAC tokenization
  -> PostgreSQL secure_login schema
  -> FastAPI technical surface
```

The pipeline stores raw sensitive identifiers only at the source boundary. Curated rows contain deterministic tokens, normalized event fields, source hashes, and audit metadata.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `src/pramanaledger/` | Runtime settings, SQS intake, validation, tokenization, PostgreSQL writes, batch runner |
| `contracts/v1/` | Versioned login-event JSON Schema |
| `sql/` | PostgreSQL schema for curated, quarantine, audit, and health objects |
| `sample_data/` | Small deterministic synthetic login-event fixture |
| `scripts/` | Sample generation, offline RBA preparation, offline execution, smoke test |
| `docs/artifacts/rba_offline/` | Compact evidence from a local RBA run |
| `docs/wiki/` | Technical notes and knowledge-bank content used by the demo surface |
| `tests/` | Unit tests for validation, tokenization, source preparation, and fetch entrypoints |
| `demo_api.py` | FastAPI presentation and inspection surface |

## Data Contract

Required fields:

| Field | Rule |
| --- | --- |
| `user_id` | Required, non-blank |
| `device_type` | `ios`, `android`, or `web` |
| `device_id` | Required, tokenized before curated persistence |
| `ip` | Required, tokenized before curated persistence |
| `locale` | Required string |
| `app_version` | Required semantic version; major version is extracted |

Optional fields:

| Field | Rule |
| --- | --- |
| `event_time_utc` | Used when present, otherwise ingestion time is used |
| `auth_result` | `success` or `failure`; defaults to `success` |
| `risk_band` | `low`, `medium`, or `high`; defaults to `low` |

Invalid events are quarantined with the original payload and error message. They are not silently coerced into placeholder records.

## Database Model

Target schema: `secure_login`

| Object | Purpose |
| --- | --- |
| `secure_login.user_logins` | Curated authentication-event facts with tokenized sensitive fields |
| `secure_login.quarantine_login_events` | Invalid payloads and validation failures |
| `secure_login.ingestion_audit` | Batch-level ingestion evidence |
| `secure_login.vw_ingestion_health` | Latest run, loaded totals, rejected totals, and batch count |

## Local Setup

Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
```

Start local services:

```powershell
docker compose up -d
```

Create the LocalStack queue:

```powershell
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name login-queue
```

Run the ingestion worker:

```powershell
$env:PYTHONPATH = "src"
python code_fetch_vaddhiparthy.py
```

Run the demo API:

```powershell
uvicorn demo_api:app --reload --port 8075
```

Local URLs:

- Demo API: `http://127.0.0.1:8075`
- Health: `http://127.0.0.1:8075/health`
- Uptime-style health: `http://127.0.0.1:8075/healthz`

## Configuration

Use `.env.example` as the template. Keep real values in ignored `.env` files or secret managers.

| Variable | Purpose |
| --- | --- |
| `SQS_ENDPOINT_URL` | LocalStack or AWS SQS endpoint |
| `SQS_QUEUE_URL` | Login-event queue URL |
| `MAX_MESSAGES` | Batch receive size |
| `WAIT_TIME_SECONDS` | SQS long-poll wait time |
| `VISIBILITY_TIMEOUT` | SQS visibility timeout |
| `DB_HOST` / `DB_PORT` / `DB_NAME` | PostgreSQL connection target |
| `DB_USER` / `DB_PASSWORD` | PostgreSQL credentials |
| `DB_SCHEMA` | Target schema, default `secure_login` |
| `HASH_SECRET` | Secret used for deterministic HMAC tokenization |
| `QUARANTINE_INVALID_EVENTS` | Whether rejected messages are deleted after quarantine |

## Validation

```powershell
python -m unittest discover -s tests -p "test_*.py"
Get-ChildItem src\pramanaledger\*.py | ForEach-Object { python -m py_compile $_.FullName }
python -m py_compile code_fetch_vaddhiparthy.py demo_api.py
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
```

The smoke script runs unit tests and compiles the runtime modules. It does not require real cloud credentials.

## RBA Dataset Path

The repository includes an adapter for the DAS Group Login Data Set for Risk-Based Authentication.

Dataset references:

- Kaggle: `dasgroup/rba-dataset`
- Zenodo DOI: `10.5281/zenodo.6782156`

The full dataset is not committed. To activate it locally:

```powershell
mkdir data\external\rba
$env:PYTHONPATH = "src"
python scripts\prepare_rba_dataset.py `
  --source data\external\rba\rba-dataset.zip `
  --output data\external\rba\login_events.normalized.jsonl `
  --limit 5000
```

Offline run:

```powershell
$env:PYTHONPATH = "src"
python scripts\run_offline_rba_pipeline.py `
  --source data\external\rba\rba-dataset.zip `
  --artifacts-dir data\artifacts\rba_offline `
  --limit 100000 `
  --preview-rows 1000
```

Committed compact artifacts under `docs/artifacts/rba_offline/` show the output shape without committing the full source dataset.

## Security Notes

- Do not commit `.env` files, raw credentials, live authentication logs, or downloaded RBA source files.
- Curated rows must use `masked_ip` and `masked_device_id`, not raw IP or device identifiers.
- Replay behavior depends on deterministic event identity; changes to canonical hashing or HMAC secrets affect deduplication.
- Quarantine exists to preserve evidence for malformed records without letting them enter the curated table.
