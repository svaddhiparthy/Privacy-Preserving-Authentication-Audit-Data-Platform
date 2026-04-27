import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pramanaledger.transform import transform_event, validate_event


app = FastAPI(title="PramanaLedger Authentication Audit Platform")


class DemoEvent(BaseModel):
    user_id: str
    device_type: str
    device_id: str
    ip: str
    locale: str
    app_version: str


def _read_text(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _sample_events() -> list[dict]:
    rows = []
    for line in _read_text("sample_data/login_events.jsonl").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _transformed_events() -> list[dict]:
    batch_id = "demo-batch-001"
    return [transform_event(event, batch_id=batch_id) for event in _sample_events()]


def _audit_rows() -> list[dict]:
    rows = _transformed_events()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return [
        {
            "batch_id": "demo-batch-001",
            "started_at_utc": now,
            "completed_at_utc": now,
            "messages_received": len(rows),
            "records_loaded": len(rows),
            "records_rejected": 0,
        }
    ]


@app.get("/", response_class=HTMLResponse)
def demo_page() -> str:
    return _read_text("docs/demo.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "pramanaledger-demo"}


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "pramanaledger-demo"}


@app.get("/api/platform-summary")
def platform_summary() -> dict:
    transformed = _transformed_events()
    return {
        "project": "Privacy Preserving Authentication Audit Data Platform",
        "internal_name": "PramanaLedger",
        "public_route": "https://surya.vaddhiparthy.com/privacy-preserving-authentication-audit-data-platform",
        "purpose": "A governed authentication-event ingestion platform that validates login telemetry, tokenizes sensitive identifiers, preserves audit evidence, and produces curated security analytics tables.",
        "implemented_counts": {
            "source_event_examples": len(_sample_events()),
            "curated_event_examples": len(transformed),
            "sql_tables": 3,
            "sql_views": 1,
            "contract_versions": 1,
            "unit_tests": 4,
            "health_endpoints": 2,
        },
        "implemented_controls": [
            "Required-field validation",
            "Device-type domain enforcement",
            "Semantic app-version parsing",
            "Secret-salted HMAC tokenization",
            "Deterministic event identity for replay safety",
            "Quarantine path for rejected records",
            "Batch-level audit evidence",
        ],
    }


@app.get("/api/flow")
def flow() -> dict:
    return {
        "stages": [
            {
                "stage": "Source Contract",
                "tooling": "JSON Schema, producer contract",
                "artifact": "contracts/v1/login_event.schema.json",
                "output": "LoginEvent payload with required identity, device, IP, locale, and app version fields",
            },
            {
                "stage": "Queue Ingestion",
                "tooling": "AWS SQS compatible client, LocalStack for local execution",
                "artifact": "src/pramanaledger/sqs.py",
                "output": "Bounded message batch with explicit receive and delete behavior",
            },
            {
                "stage": "Validation",
                "tooling": "Python validation layer",
                "artifact": "src/pramanaledger/transform.py",
                "output": "Accepted payloads continue; malformed payloads are routed to quarantine",
            },
            {
                "stage": "Privacy Transform",
                "tooling": "HMAC-SHA256",
                "artifact": "src/pramanaledger/tokenization.py",
                "output": "Raw IP and device identifiers replaced with deterministic irreversible tokens",
            },
            {
                "stage": "Curated Persistence",
                "tooling": "PostgreSQL",
                "artifact": "src/pramanaledger/postgres.py",
                "output": "secure_login.user_logins, secure_login.quarantine_login_events, secure_login.ingestion_audit",
            },
            {
                "stage": "Operations Surface",
                "tooling": "FastAPI, Docker, Caddy",
                "artifact": "demo_api.py, Dockerfile, docker-compose.prod.yml",
                "output": "Public demo, health checks, contract browser, table previews, and platform documentation",
            },
        ]
    }


@app.get("/api/architecture")
def architecture() -> dict:
    return {
        "layers": [
            "source contract",
            "queue-backed bronze intake",
            "validation and quarantine",
            "privacy-preserving silver model",
            "audit and health evidence",
            "public technical surface",
        ],
        "system_positioning": "Secure event ingestion platform with privacy controls, idempotent writes, observability, and auditability.",
    }


@app.get("/api/stack")
def stack() -> dict:
    return {
        "implemented": [
            {"tool": "AWS SQS compatible ingestion", "role": "Queue-backed authentication event intake with local execution through LocalStack"},
            {"tool": "Python", "role": "Validation, deterministic event identity, PII tokenization, and batch orchestration"},
            {"tool": "PostgreSQL", "role": "Curated login fact, quarantine table, ingestion audit table, and health view"},
            {"tool": "FastAPI", "role": "Public technical surface, live transform preview, and health endpoints"},
            {"tool": "Docker Compose", "role": "Repeatable local services and production web container"},
            {"tool": "Caddy", "role": "Portfolio-domain reverse proxy and TLS edge routing"},
        ],
        "planned": [
            {"tool": "dbt", "role": "Bronze, silver, and gold transformations with relationship and freshness tests"},
            {"tool": "Airflow", "role": "Scheduled ingestion, retries, backfills, and run history"},
            {"tool": "S3", "role": "Immutable landing zone for source contracts, raw batches, and retained audit exports"},
            {"tool": "OpenLineage-compatible model", "role": "Dataset, job, and run-level lineage representation"},
            {"tool": "Monitoring", "role": "Reject rate, batch freshness, queue depth, and endpoint availability checks"},
        ],
    }


@app.get("/api/quality-gates")
def quality_gates() -> dict:
    return {
        "gates": [
            {
                "gate": "Required field presence",
                "implemented_in": "src/pramanaledger/transform.py",
                "failure_behavior": "Reject event and persist reason in quarantine path",
            },
            {
                "gate": "Device type domain validation",
                "implemented_in": "src/pramanaledger/transform.py",
                "failure_behavior": "Reject values outside ios, android, and web",
            },
            {
                "gate": "App version normalization",
                "implemented_in": "src/pramanaledger/transform.py",
                "failure_behavior": "Reject malformed semantic version strings",
            },
            {
                "gate": "PII exclusion from curated model",
                "implemented_in": "src/pramanaledger/tokenization.py",
                "failure_behavior": "Raw IP and device identifiers are replaced before insertion",
            },
            {
                "gate": "Idempotent replay",
                "implemented_in": "src/pramanaledger/postgres.py",
                "failure_behavior": "Duplicate event_id writes are ignored instead of duplicated",
            },
            {
                "gate": "Batch audit trail",
                "implemented_in": "src/pramanaledger/postgres.py",
                "failure_behavior": "Each run writes received, loaded, and rejected counts",
            },
        ],
        "metrics": {
            "freshness_sla_minutes": 15,
            "max_reject_rate_percent": 2,
            "duplicate_handling": "ON CONFLICT DO NOTHING on event_id",
            "replay_mode": "safe because event_id is deterministic",
        },
    }


@app.get("/api/sample-events")
def sample_events() -> dict:
    return {"records": _sample_events()}


@app.get("/api/sample-transform")
def sample_transform() -> dict:
    return {"records": _transformed_events()}


@app.get("/api/table-preview")
def table_preview() -> dict:
    return {
        "tables": [
            {
                "name": "secure_login.user_logins",
                "purpose": "Curated analytics-ready login fact table with sensitive identifiers tokenized.",
                "columns": [
                    "event_id",
                    "batch_id",
                    "user_id",
                    "device_type",
                    "masked_ip",
                    "masked_device_id",
                    "locale",
                    "app_version",
                    "app_version_raw",
                    "source_event_hash",
                    "pii_strategy",
                    "create_date",
                    "ingested_at_utc",
                ],
                "sample_rows": _transformed_events(),
            },
            {
                "name": "secure_login.ingestion_audit",
                "purpose": "Batch control table for load counts, reject counts, and freshness evidence.",
                "columns": [
                    "batch_id",
                    "started_at_utc",
                    "completed_at_utc",
                    "messages_received",
                    "records_loaded",
                    "records_rejected",
                ],
                "sample_rows": _audit_rows(),
            },
            {
                "name": "secure_login.quarantine_login_events",
                "purpose": "Rejected payloads with error messages for operational triage and replay governance.",
                "columns": ["quarantine_id", "batch_id", "rejected_at_utc", "error_message", "payload"],
                "sample_rows": [],
            },
        ]
    }


@app.get("/api/sql-schema", response_class=PlainTextResponse)
def sql_schema() -> str:
    return _read_text("sql/001_secure_login_schema.sql")


@app.get("/api/source-contract")
def source_contract() -> dict:
    return json.loads(_read_text("contracts/v1/login_event.schema.json"))


@app.get("/api/wiki", response_class=PlainTextResponse)
def wiki() -> str:
    return _read_text("docs/wiki/privacy_preserving_authentication_audit_data_platform.txt")


@app.get("/api/working-notes", response_class=PlainTextResponse)
def working_notes() -> str:
    return _read_text("docs/wiki/privacy_preserving_authentication_audit_data_platform_working_notes.txt")


@app.post("/api/validate")
def validate(payload: DemoEvent) -> dict:
    event = payload.model_dump()
    validate_event(event)
    return {"valid": True, "transformed": transform_event(event, batch_id="interactive-demo")}
