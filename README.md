# Privacy Preserving Authentication Audit Data Platform

[![CI](https://github.com/Vaddhiparthy/Privacy-Preserving-Authentication-Audit-Data-Platform/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Vaddhiparthy/Privacy-Preserving-Authentication-Audit-Data-Platform/actions/workflows/ci.yml)

A batch data pipeline for authentication telemetry. Login events arrive on an SQS-compatible
queue, are checked against a versioned data contract, have their direct identifiers replaced
with keyed HMAC tokens, and land in PostgreSQL as a curated fact table. Records that fail the
contract are quarantined with the failure reason rather than coerced into placeholder values,
and every run writes a batch-level audit row. A FastAPI service exposes the contract, the SQL
schema, column lineage and run evidence for inspection.

The Python package is `authaudit` and the runtime is Python 3.11.

Project page: [vaddhiparthy.com/privacy-preserving-authentication-audit-data-platform](https://vaddhiparthy.com/privacy-preserving-authentication-audit-data-platform/)

```bash
curl -fsS "https://vaddhiparthy.com/privacy-preserving-authentication-audit-data-platform/healthz"
```

## Data flow

One invocation of the worker processes one batch. Nothing is long-running.

```text
producer
   |  JSON message body
   v
SQS-compatible queue  ......................................  authaudit.sqs
   |  receive_message, long poll, at most MAX_MESSAGES per call
   v
validate_event  ............ rejects ....> quarantine rows ..  authaudit.transform
   |  passes                               payload + reason
   v
transform_event  ...........................................  authaudit.transform
   |  masked_ip        = HMAC-SHA256(ip, HASH_SECRET)
   |  masked_device_id = HMAC-SHA256(device_id, HASH_SECRET)
   |  event_id         = HMAC-SHA256(SHA-256(canonical payload), HASH_SECRET)
   v
PostgreSQL, schema secure_login  ...........................  authaudit.postgres
   |
   +--> user_logins                INSERT ... ON CONFLICT (event_id) DO NOTHING
   +--> quarantine_login_events    one row per rejected message
   +--> ingestion_audit            one row per batch, ON CONFLICT (batch_id) DO NOTHING
   |
   v
delete_message_batch for every settled receipt handle  .....  authaudit.sqs
   |
   v
FastAPI inspection endpoints  ..............................  authaudit.api
```

Batch orchestration lives in `authaudit.runner`. A message is deleted from the queue once it
has been settled, meaning it was either loaded or quarantined; setting
`QUARANTINE_INVALID_EVENTS=false` keeps rejected messages on the queue instead. A message
without a receipt handle is skipped and logged, because it cannot be deleted and would
otherwise redeliver forever.

## Data contract

The published contract is JSON Schema 2020-12 at `contracts/v1/login_event.schema.json`. The
directory is versioned, so a breaking change lands as `contracts/v2/` rather than an edit in
place.

| Field | Required | Rule |
|---|---|---|
| `user_id` | yes | Non-blank string. Carried into the curated table unchanged; it is the analytic grain. |
| `device_type` | yes | Closed set: `ios`, `android`, `web`. |
| `device_id` | yes | Tokenized before persistence. |
| `ip` | yes | Tokenized before persistence. |
| `locale` | yes | Locale string such as `en_US`. |
| `app_version` | yes | Major component must parse to an integer; both the integer and the raw string are stored. |
| `event_time_utc` | no | Producer event time. Defaults to ingestion time when absent, and is kept in a separate column from `ingested_at_utc`. |
| `auth_result` | no | `success` or `failure`. Defaults to `success`. |
| `risk_band` | no | `low`, `medium`, `high`. Defaults to `low`. |

Enforcement is `authaudit.transform.validate_event`, a plain Python check rather than a
runtime schema validator. It is a near-subset of the schema: it does not re-check the
`app_version` regex or the minimum `locale` length, so `5.2.3.4` is accepted by the worker and
rejected by the schema. CI asserts the schema file stays valid and keeps its required set.

A rejected event is written to `secure_login.quarantine_login_events` with the original payload
as `jsonb` and the exception text as `error_message`, and the batch continues. One bad record
never fails a batch. A message body that is not valid JSON at all is a different case: it
raises out of `parse_messages` before any write, so the batch aborts and the messages stay on
the queue for redelivery.

## Idempotency and replay safety

Event identity is derived, not accepted from the producer:

1. `canonical_event_hash` serializes the source payload with sorted keys and no whitespace, then
   takes SHA-256. Key order in the incoming JSON cannot change the result.
2. `event_id` is HMAC-SHA256 over that hash, keyed by `HASH_SECRET`.
3. `event_id` is the primary key of `secure_login.user_logins`, and inserts use
   `ON CONFLICT (event_id) DO NOTHING`.

A redelivered or replayed message therefore produces the same key and is a no-op at the storage
boundary, with no upstream dedupe state to keep. The same applies to audit rows: `batch_id` is
the primary key of `secure_login.ingestion_audit` and its insert also uses
`ON CONFLICT DO NOTHING`, so rerunning a batch cannot double-count it.

Because tokenization and event identity are pure functions of the payload and the secret, a
batch can be resharded across processes without coordination.

## Privacy model

`masked_ip` and `masked_device_id` are keyed HMAC-SHA256, not bare hashes: a bare SHA-256 of an
IPv4 address falls to a sweep of a 32-bit space, whereas keying it leaves the token opaque
without the key and still stable enough to join on repeat visits. Every curated row carries
`pii_strategy = hmac_sha256_secret_salted`, so a future strategy change stays distinguishable at
row level. `user_id` is carried through unchanged; it is pseudonymous in the source and is
deliberately kept joinable, so the claim here is identifier minimization, not anonymization.

Column-level lineage for all sixteen curated columns is declared in `authaudit.lineage`, beside
the transform it describes, so it is reviewed in the same diff as the code that produces it.
Each entry states its source fields, its rule, and whether it carries an identifier;
`tests/test_lineage.py` asserts the map covers every curated column exactly once and that
neither direct identifier is carried raw.

## Table reference

Schema `secure_login`, created by `sql/001_secure_login_schema.sql` and by
`authaudit.postgres.ensure_table_exists` at run time. Every statement is `IF NOT EXISTS` or
`CREATE OR REPLACE`, so the worker is safe to start against an existing database.

| Object | Grain | Holds |
|---|---|---|
| `user_logins` | One row per distinct source payload, keyed by `event_id` | Curated login fact: `user_id`, `device_type`, `locale`, `auth_result`, `risk_band`, parsed and raw app version, tokenized IP and device, `source_event_hash`, `pii_strategy`, `batch_id`, event time and ingestion time |
| `quarantine_login_events` | One row per rejected message, keyed by `quarantine_id` | Original payload as `jsonb`, validation `error_message`, `batch_id`, rejection timestamp |
| `ingestion_audit` | One row per batch run, keyed by `batch_id` | Start and completion timestamps, `messages_received`, `records_loaded`, `records_rejected` |
| `vw_ingestion_health` | One row, aggregate over `ingestion_audit` | Last completed load, total loaded, total rejected, batch count |

`source_event_hash` is the unkeyed canonical hash, which lets a quarantined payload be matched
to a curated row without storing either in the other table.

## Inspection API

`authaudit.api` serves a read-only FastAPI surface over the same code paths the worker uses.

| Endpoint | Returns |
|---|---|
| `GET /healthz`, `GET /health` | Liveness, used by the container healthcheck and by CI |
| `GET /api/source-contract` | The JSON Schema contract |
| `GET /api/sql-schema` | The SQL DDL as plain text |
| `GET /api/lineage` | Column lineage and its computed summary |
| `GET /api/quality-gates` | Each gate, the module implementing it, and its failure behaviour |
| `GET /api/operations` | Scheduling, run history with freshness, failure modes, measured scale |
| `GET /api/sample-events`, `GET /api/sample-transform` | Source rows and the curated rows they produce |
| `GET /api/table-preview` | First ten rows of each packaged offline artifact |
| `POST /api/validate` | Validates one event and returns either the curated row or the rejection reason the quarantine table would record |

## Source data

Sample surfaces read a normalized external dataset when one is present under
`data/external/rba/`, fall back to the packaged offline artifact, and finally to the 120-row
fixture in `sample_data/login_events.jsonl`.

The external source is the Login Data Set for Risk-Based Authentication, published under
CC BY 4.0 with DOI `10.5281/zenodo.6782156`. It is not committed; the repository carries the
adapter and the column mapping. `authaudit.sources` streams the CSV or zip and maps it onto the
contract: user and device attributes become `user_id`, `device_type` and a composite
`device_id`, the IP is carried for tokenization, country becomes `locale`, login success becomes
`auth_result`, and the attack-IP and account-takeover flags collapse into `risk_band`.

To use it locally, place the archive under `data/external/rba/` and normalize it onto the
contract:

```powershell
python scripts/prepare_rba_dataset.py --source data/external/rba/rba-dataset.zip
```

`scripts/run_offline_rba_pipeline.py` then runs the same transform over that archive with no
queue, no database and no cloud services, writing artifacts to disk. The committed run in
`docs/artifacts/rba_offline/` recorded:

| Measure | Value |
|---|---|
| Records processed | 100,000 |
| Records rejected | 0 |
| Execution time | 5.16 s single process, about 19.4k records/second |
| Unique users resolved | 41,500 |
| Outputs | Bronze and silver JSONL previews, audit CSV, metrics, table inventory, manifest |

These numbers describe one offline run against files, not a load into PostgreSQL. The artifact
directory holds preview slices, not the full 100,000 rows.

## Local development

Everything below runs on the local machine only. The endpoints in this section are local
development addresses and are not a public surface.

Start PostgreSQL and LocalStack, then install the package and dev tooling:

```powershell
docker compose up -d
pip install -e ".[dev]"
```

Create the local queue and send one event:

```powershell
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name login-queue

aws --endpoint-url=http://localhost:4566 sqs send-message `
  --queue-url http://localhost:4566/000000000000/login-queue `
  --message-body '{\"user_id\":\"user_123\",\"device_type\":\"android\",\"device_id\":\"A1B2C3D4\",\"ip\":\"192.168.1.10\",\"locale\":\"en_US\",\"app_version\":\"5.2.3\"}'
```

Run one ingestion batch, then the inspection API:

```powershell
python -m authaudit.runner
uvicorn authaudit.api:app --reload --port 8075
```

The local API is then on `http://127.0.0.1:8075`.

## Configuration

Configuration is environment-driven. `.env.example` is the template; real values belong in an
ignored `.env`.

| Variable | Purpose |
|---|---|
| `SQS_ENDPOINT_URL`, `SQS_QUEUE_URL` | Queue endpoint and login-event queue URL |
| `MAX_MESSAGES`, `WAIT_TIME_SECONDS`, `VISIBILITY_TIMEOUT` | Receive batch size, long-poll wait and visibility timeout; defaults 10, 1, 30 |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL connection |
| `DB_SCHEMA` | Target schema, default `secure_login` |
| `HASH_SECRET` | Key for HMAC tokenization and event identity |
| `QUARANTINE_INVALID_EVENTS` | Whether rejected messages are deleted from the queue after quarantine, default true |

`HASH_SECRET` is resolved from the environment on every call, so a deployment cannot be pinned
to an import-time default. When it is unset the package falls back to a development constant,
and tokens produced with that fallback are reproducible by anyone;
`authaudit.config.hash_secret_is_demo()` reports whether the fallback is in force. No real
secret belongs in committed code, SQL, markdown, logs or the Docker build context.

## Testing

```powershell
ruff check .
pytest
python scripts/check_test_count.py
```

84 tests across nine modules, all runnable without a database or a queue:

| Module | Covers |
|---|---|
| `test_transform.py` | Validation rules, canonical hashing, tokenization of the curated row, replay determinism |
| `test_api.py` | Endpoint contracts, packaged artifacts, published metrics, no raw identifier in any response |
| `test_postgres.py` | SQL statements asserted through a recording cursor: idempotent DDL, `ON CONFLICT` behaviour, quarantine and audit writes |
| `test_tokenization.py` | HMAC matches the standard library, is key-dependent, and is not a plain hash |
| `test_operations.py` | Every published failure mode names a real file and states a blast radius |
| `test_lineage.py` | Lineage covers every curated column once and carries no raw identifier |
| `test_sqs.py` | Receipt-handle pairing, ordering, malformed bodies |
| `test_sources.py` | External dataset mapping into the contract |
| `test_public_identity.py` | The served page resolves identity from site content rather than hard-coding it |

`scripts/check_test_count.py` is the gate that keeps the published figure honest: it collects
the suite with pytest and fails if the count differs from `TEST_COUNT` in
`src/authaudit/api.py`, which is what the project page reports. `--write` updates the constant.
If the suite size changes, that constant and this section change with it.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and on pull requests into `main`.

| Job | Does |
|---|---|
| Lint | `ruff check .` pinned to ruff 0.8.6 on Python 3.11 |
| Tests | Installs the package with dev extras, runs pytest, then the test-count gate |
| Contract and artifact checks | Asserts the login-event schema is loadable JSON Schema with its required set intact, and that the published audit evidence carries no operator filesystem path |
| Docker build | On `main` only, after lint and tests: builds the image, starts the container, and polls the health endpoint until it answers |

## Repository layout

```text
src/authaudit/
  config.py        environment-backed settings and secret resolution
  tokenization.py  SHA-256 and HMAC-SHA256 primitives
  transform.py     contract validation, canonical hashing, curated row construction
  sqs.py           queue receive, parse, batch delete
  postgres.py      schema DDL and the three write paths
  runner.py        one batch: receive, transform, persist, audit, settle
  lineage.py       declared column lineage for the curated table
  operations.py    failure modes, scheduling, measured scale
  sources.py       external dataset adapter
  api.py           FastAPI inspection surface

contracts/v1/      versioned JSON Schema contract
sql/               PostgreSQL DDL and the health view
scripts/           sample generation, dataset preparation, offline run, test-count gate
sample_data/       120-row deterministic fixture
docs/              served page, knowledge bank, offline run artifacts
tests/             unit tests
```

## Scope

Implemented: queue intake, contract validation, HMAC tokenization, deterministic event identity,
curated and quarantine and audit tables, an offline execution path, and a read-only inspection
API. What this is not:

- Not a streaming system. One batch per invocation, triggered on demand; no scheduler here.
- Not a PII vault. No controlled re-identification path and no access audit around one; the
  secret that keys the tokens is not managed in this repository.
- Not warehouse-modelled. No dbt models and no gold marts; bronze and silver naming appears only
  in the offline artifacts.
- Not integration-tested against a live database. Persistence is asserted at the SQL-statement
  level through a recording cursor, which keeps the suite runnable in CI without a server.
