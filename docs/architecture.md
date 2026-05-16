# Architecture

The pipeline is organized around authentication-event intake, validation, privacy transformation, curated persistence, and audit evidence.

```text
Source event
  -> SQS-compatible queue
  -> ingestion worker
  -> validation and quarantine decision
  -> HMAC tokenization
  -> secure_login PostgreSQL schema
  -> FastAPI technical surface
```

## Runtime Components

| Component | Path | Role |
| --- | --- | --- |
| Settings | `src/pramanaledger/config.py` | Loads queue, database, and tokenization configuration |
| Queue client | `src/pramanaledger/sqs.py` | Receives and deletes SQS-compatible messages |
| Transform layer | `src/pramanaledger/transform.py` | Validates fields, normalizes event values, generates event identity |
| Tokenization | `src/pramanaledger/tokenization.py` | Produces deterministic SHA-256 and HMAC-SHA256 values |
| Persistence | `src/pramanaledger/postgres.py` | Creates schema objects and writes curated, quarantine, and audit rows |
| Runner | `src/pramanaledger/runner.py` | Coordinates a bounded ingestion batch |
| Demo API | `demo_api.py` | Exposes health, flow, contract, preview, and table-inspection endpoints |

## Data Boundary

Raw authentication attributes are accepted only at ingestion and preview boundaries. The curated table stores:

- deterministic `event_id`;
- `masked_ip`;
- `masked_device_id`;
- normalized event fields;
- source event hash;
- batch and ingestion timestamps.

The database schema keeps rejected events separate from curated facts.

## Current Scope

Implemented scope:

- SQS-compatible batch ingestion;
- LocalStack-compatible development flow;
- required-field and domain validation;
- deterministic HMAC tokenization;
- PostgreSQL curated, quarantine, audit, and health objects;
- FastAPI inspection surface;
- offline RBA dataset adapter and compact run artifacts.

Not claimed as live:

- dbt marts;
- Airflow DAGs;
- hosted S3 lakehouse;
- privileged re-identification vault.
