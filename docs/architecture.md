# Architecture Plan

## Operating Name

Formal name:

```text
Privacy Preserving Authentication Audit Data Platform
```

Internal name:

```text
Privacy-Preserving Authentication Audit Data Platform
```

Public slug:

```text
privacy-preserving-authentication-audit-data-platform
```

## Purpose

The platform is a secure authentication-event ingestion and audit system. It demonstrates the engineering controls that a regulated environment expects around authentication data: contract validation, PII minimization, deterministic replay safety, quarantine handling, auditability, and operational evidence.

The project starts from a working local pipeline and will expand in controlled slices. The design goal is not to add tooling for its own sake. Every component must either protect sensitive data, improve pipeline reliability, expose operational evidence, or make the data model more maintainable.

## Current Data Flow

```text
Login event message
        |
        v
SQS-compatible queue
        |
        v
Batch ingestion worker
        |
        +--> validate required fields
        +--> validate device type
        +--> parse app version
        +--> HMAC-tokenize IP and device ID
        +--> generate deterministic event_id
        |
        v
PostgreSQL secure_login schema
        |
        +--> user_logins
        +--> quarantine_login_events
        +--> ingestion_audit
```

## Target Expansion Architecture

```text
Source queue
    |
    v
Contract validation
    |
    +--> quarantine
    |
    v
Tokenization and event identity
    |
    +--> PII vault access boundary
    |
    v
Bronze raw retention
    |
    v
Silver validated records
    |
    v
Gold audit marts
    |
    +--> FastAPI
    +--> Streamlit operational surface
    +--> Streamlit technical surface
    +--> Wiki knowledge bank
```

## Scope Boundary

The expansion architecture in this document is the target roadmap, not a claim that every module is live today. The current deployed implementation covers the secure ingestion core: queue-compatible intake, validation, HMAC tokenization, curated persistence, quarantine handling, audit evidence, health endpoints, and a public technical surface.

Modules such as PII vault, Airflow, dbt, S3 lakehouse storage, and monitoring remain planned until their executable code paths, smoke tests, and public evidence pages are present.

## Expansion Slices

| Slice | Scope | Validation target |
|---|---|---|
| 1 | Package refactor | Existing unit tests unchanged |
| 2 | Local runtime foundation | Docker Compose, API health, smoke test |
| 3 | Source contracts | Valid and invalid contract fixtures |
| 4 | PII vault | RBAC denial, audit row creation, re-identification path |
| 5 | dbt modeling | Mart tests and no-raw-PII invariant |
| 6 | Airflow orchestration | DAG import and task command validation |
| 7 | Streamlit surfaces | App startup and table preview smoke test |
| 8 | Wiki and README | Documentation scan and link consistency |
| 9 | Deployment | Public route and health endpoint checks |

## Cloud Posture

The project is local-first. LocalStack is the default for AWS-compatible services. The existing S3 bucket family can be reused later under a project-specific prefix:

```text
s3://finlens-vaddhiparthy-vip-raw/pramana-ledger/bronze/
s3://finlens-vaddhiparthy-vip-raw/pramana-ledger/silver/
s3://finlens-vaddhiparthy-vip-raw/pramana-ledger/gold/
s3://finlens-vaddhiparthy-vip-raw/pramana-ledger/reports/
```

No cloud mirror is required for the first working build.

## External Dataset Activation

The primary external dataset target is the Login Data Set for Risk-Based Authentication from DAS Group. It is directly aligned with this platform because it contains synthesized login attempts, IP-derived geography, ASN, user agent attributes, user identifiers, login timestamps, round-trip time, login success, attack-IP flags, and account-takeover labels.

The adapter is implemented in `src/pramanaledger/sources.py`. It normalizes the Kaggle or Zenodo CSV/zip into the same JSONL contract used by the ingestion worker. The API checks for `data/external/rba/login_events.normalized.jsonl` and uses that file when present; otherwise, it falls back to the repository fixture.

The full RBA dataset is intentionally not committed because it is large. The repository carries the adapter, contract mapping, and activation instructions.

## Offline Execution Evidence

The project has a local-only RBA execution script:

```text
scripts/run_offline_rba_pipeline.py
```

It reads the downloaded RBA zip directly from disk, streams rows through the source adapter, executes the same transform code used by the service, and writes local artifacts. No AWS, S3, hosted queues, or remote warehouses are used in this mode.

The latest run processed 100,000 RBA records and wrote:

```text
docs/artifacts/rba_offline/offline_run_manifest.json
docs/artifacts/rba_offline/offline_run_metrics.json
docs/artifacts/rba_offline/table_inventory.json
docs/artifacts/rba_offline/audit_ingestion_runs.csv
docs/artifacts/rba_offline/bronze_rba_login_events_sample.jsonl
docs/artifacts/rba_offline/silver_user_logins_sample.jsonl
```
