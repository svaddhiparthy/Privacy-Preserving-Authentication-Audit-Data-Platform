# Architecture Plan

## Operating Name

Formal name:

```text
Privacy Preserving Authentication Audit Data Platform
```

Internal name:

```text
PramanaLedger
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
