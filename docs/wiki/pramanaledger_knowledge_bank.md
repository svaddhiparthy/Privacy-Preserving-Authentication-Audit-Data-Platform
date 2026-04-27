# PramanaLedger Knowledge Bank

## Project Thesis

PramanaLedger is a privacy-preserving authentication audit data platform. The core business problem is simple: authentication telemetry is operationally valuable, but it contains sensitive identifiers that should not be copied directly into analytical tables. The platform demonstrates how a data engineer can accept raw login events, validate them, minimize sensitive fields, preserve rejected records for investigation, and maintain auditable evidence for every load.

The project is intentionally positioned as a banking-style data engineering system. It is not a dashboard-first product. The main artifact is the data platform: source contract, queue ingestion, validation, privacy transform, curated storage, quarantine storage, audit evidence, and an operational surface that proves the pipeline behavior.

## Implemented Scope

| Capability | Current state | Evidence |
|---|---|---|
| Source contract | Implemented | `contracts/v1/login_event.schema.json` |
| Queue-backed ingestion | Implemented locally | `src/pramanaledger/sqs.py` |
| Validation layer | Implemented | `src/pramanaledger/transform.py` |
| PII tokenization | Implemented | `src/pramanaledger/tokenization.py` |
| Curated persistence | Implemented | `src/pramanaledger/postgres.py` |
| Quarantine persistence | Implemented | `secure_login.quarantine_login_events` |
| Batch audit evidence | Implemented | `secure_login.ingestion_audit` |
| Health endpoint | Implemented | `/healthz` |
| Public technical surface | Implemented | FastAPI + Docker + Caddy |
| Synthetic telemetry set | Implemented | `sample_data/login_events.jsonl` |

## Source Data Strategy

The live page can use two source modes. The default mode uses deterministic synthetic authentication telemetry stored in the repository. The external mode uses the Login Data Set for Risk-Based Authentication from DAS Group, available through Kaggle and Zenodo.

The RBA dataset is a strong fit because it contains synthesized login attempts with IP address, country, region, city, ASN, user agent string, operating system, browser, device type, user ID, login timestamp, round-trip time, login success, attack-IP indicator, and account-takeover indicator. Those fields map naturally into the PramanaLedger contract and make the project more than a two-row demonstration.

The full dataset is large, so the repository carries an adapter instead of committing the data. When `data/external/rba/login_events.normalized.jsonl` is present, the API switches from the local fixture to the normalized RBA sample automatically.

The project can later add public reference data without changing the core design. Good candidates are IP geolocation reference tables, autonomous-system lookup data, device taxonomy mappings, country and locale reference data, and public security-control frameworks. Those enrich the platform without requiring private login data.

## Why HMAC Tokenization

Plain hashing is not enough for small input spaces. IPv4 addresses and common device identifiers can be brute-forced or dictionary-attacked if the hash is unsalted. PramanaLedger uses secret-keyed HMAC-SHA256 so the same input produces a stable token only when the secret is known.

This gives the platform two important properties. First, the token is deterministic, so repeated appearances of the same IP or device can still be joined analytically. Second, the raw value is not stored in the curated analytical table, so routine reporting does not expose direct identifiers.

## Event Identity and Replay Safety

The event identity is derived from a canonical source-event hash and a secret HMAC key. This avoids dependency on source-provided event IDs, which are often missing or inconsistent in operational telemetry. If the same event is replayed, it produces the same `event_id`.

The database layer enforces idempotency through `ON CONFLICT DO NOTHING`. That matters because queues and streaming systems can redeliver messages. Replay safety belongs at the storage boundary, not only in application memory.

## Validation and Quarantine

The validation layer enforces required fields, expected device types, and parseable application versions. The important design choice is that invalid records are rejected rather than silently coerced. A malformed device type is not converted to `unknown`; it is routed into quarantine with an error message.

This pattern protects analytical quality. Analysts can trust that curated rows passed the minimum contract, while operations can still inspect rejected payloads and decide whether the producer contract or the data itself needs correction.

## Database Model

The implemented schema is `secure_login`.

| Object | Purpose |
|---|---|
| `secure_login.user_logins` | Curated authentication fact table with tokenized identifiers |
| `secure_login.quarantine_login_events` | Rejected payload table with validation reason |
| `secure_login.ingestion_audit` | Batch control table with received, loaded, and rejected counts |
| `secure_login.vw_ingestion_health` | Operational rollup for latest load and cumulative counts |

The model is intentionally small. It demonstrates a production-shaped triad: curated table, quarantine table, and audit table. That is more credible than a single flat table because it shows how the platform behaves when data is imperfect.

## Quality Controls

| Control | Purpose |
|---|---|
| Required field validation | Prevents partial login records from entering curated storage |
| Device type domain check | Keeps downstream dimensions controlled |
| Version parsing | Converts semantic version strings into analyzable major versions |
| HMAC tokenization | Removes raw IP and device identifiers from curated storage |
| Deterministic event ID | Makes replay safe |
| Quarantine table | Preserves bad records and failure reasons |
| Ingestion audit table | Provides operational evidence for each batch |

## Current Execution Evidence

The public page exposes live API-backed sections instead of static screenshots. The transform preview calls the running service, reads repository sample events, executes the same transform function used by the worker, and returns curated output. The table browser is generated from the implemented schema and sample transform output. The source contract and SQL schema are served directly from repository assets packaged into the production image.

## Planned Expansion

| Module | Purpose | Status |
|---|---|---|
| PII vault | Controlled re-identification and access audit | Planned |
| Bronze/Silver/Gold layers | Analytical data platform structure | Planned |
| dbt | Transformation tests, documentation, and lineage | Planned |
| Airflow | Scheduling, retries, backfills, and DAG evidence | Planned |
| S3 retention | Immutable landing and retained audit exports | Planned |
| Streamlit control room | Rich operational surface | Planned |
| Monitoring | Freshness, reject rate, throughput, endpoint health | Planned |

The expansion should remain local-first. Cloud services are useful for portfolio proof, but they should not be required for development or review.

## Data Source Expansion Options

The safest near-term enhancement is not scraping a public page. The better sequence is:

1. Expand deterministic synthetic telemetry to cover more user, device, risk, and time patterns.
2. Add public reference dimensions that are stable and non-sensitive.
3. Add optional external feeds only when the license and schema are stable.

Recommended public reference candidates:

| Source type | Use in platform | Risk |
|---|---|---|
| ISO country and locale references | Normalize locale and country attributes | Low |
| Public autonomous-system reference tables | Enrich network metadata | Medium |
| Public device taxonomy mappings | Standardize device family and platform | Low |
| NIST privacy/security control references | Documentation mapping | Low |
| Public cyber ranges or authentication logs | Larger realism, but license and schema must be reviewed | Medium |

## Implementation Discipline

The platform should continue to separate implemented behavior from planned expansion. Public pages should never imply that Airflow, dbt, S3, or a PII vault are live until the code path exists and passes smoke tests. The current site therefore marks those items as planned expansion while showing working evidence for the implemented ingestion path.
