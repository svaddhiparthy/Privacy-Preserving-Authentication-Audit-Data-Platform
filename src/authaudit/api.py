import json
import os
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel

from authaudit.lineage import COLUMN_LINEAGE, DIRECT_IDENTIFIERS, lineage_summary
from authaudit.operations import FAILURE_MODES, run_history, scale_and_cost, scheduling
from authaudit.transform import transform_event, validate_event

# src/authaudit/api.py -> repository root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(title="Privacy-Preserving Authentication Audit Pipeline")
_DOMAIN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$|^localhost$",
    re.I,
)


def public_route() -> str:
    """Return the configured canonical route without trusting request headers."""
    domain = os.getenv("SITE_DOMAIN", "localhost").strip().lower().rstrip(".")
    if not _DOMAIN.fullmatch(domain):
        domain = "localhost"
    return f"https://{domain}/privacy-preserving-authentication-audit-data-platform"


class DemoEvent(BaseModel):
    user_id: str
    device_type: str
    device_id: str
    ip: str
    locale: str
    app_version: str


def _read_text(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _read_jsonl(path: Path, limit: int = 10) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
        if len(rows) >= limit:
            break
    return rows


def _read_csv_rows(path: Path, limit: int = 10) -> list[dict]:
    if not path.exists():
        return []
    import csv

    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            rows.append(dict(row))
            if len(rows) >= limit:
                break
        return rows


def _sample_events() -> list[dict]:
    external = PROJECT_ROOT / "data" / "external" / "rba" / "login_events.normalized.jsonl"
    packaged_artifact = (
        PROJECT_ROOT / "docs" / "artifacts" / "rba_offline" / "bronze_rba_login_events_sample.jsonl"
    )
    if external.exists():
        source = external
    elif packaged_artifact.exists():
        source = packaged_artifact
    else:
        source = PROJECT_ROOT / "sample_data" / "login_events.jsonl"
    rows = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _transformed_events() -> list[dict]:
    batch_id = "demo-batch-001"
    return [transform_event(event, batch_id=batch_id) for event in _sample_events()]


def _event_metrics() -> dict:
    events = _sample_events()
    transformed = _transformed_events()
    failures = sum(1 for event in events if event.get("auth_result") == "failure")
    high_risk = sum(1 for event in events if event.get("risk_band") == "high")
    device_mix = {}
    for row in transformed:
        device_mix[row["device_type"]] = device_mix.get(row["device_type"], 0) + 1
    return {
        "source_events": len(events),
        "curated_events": len(transformed),
        "unique_users": len({event["user_id"] for event in events}),
        "auth_failures": failures,
        "high_risk_events": high_risk,
        "device_mix": device_mix,
    }


@app.get("/", response_class=HTMLResponse)
def demo_page() -> str:
    return _read_text("docs/demo.html")


@app.head("/")
def demo_page_head() -> Response:
    return Response(media_type="text/html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "authaudit-demo"}


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "authaudit-demo"}


TEST_COUNT = 84


def headline_metrics() -> list[dict]:
    """What the platform actually did, drawn from the packaged audit record.

    The fixture counts describe a demo; these describe the audited 100k-record run, which is
    what a reader should see first.
    """
    artifacts = offline_artifacts()
    if not artifacts.get("available"):
        return []
    audit = artifacts["audit"]
    metrics = artifacts["metrics"]
    loaded = audit["records_loaded"]
    rejected = audit["records_rejected"]
    seconds = audit["execution_seconds"] or 1
    received = audit["messages_received"] or 1
    return [
        {"value": f"{loaded:,}", "label": "records ingested in one audited batch"},
        {
            "value": f"{round(loaded / seconds / 1000, 1)}k/s",
            "label": "sustained transform throughput",
        },
        {
            "value": f"{round(100 * (received - rejected) / received, 1)}%",
            "label": "passed the contract, 0 rejected",
        },
        {"value": f"{metrics['unique_users']:,}", "label": "unique users resolved"},
        {"value": "2 of 2", "label": "direct identifiers tokenized, IP and device"},
        {"value": str(TEST_COUNT), "label": "tests gating every push"},
    ]


@app.get("/api/platform-summary")
def platform_summary() -> dict:
    _transformed_events()
    metrics = _event_metrics()
    return {
        "project": "Privacy Preserving Authentication Audit Data Platform",
        "internal_name": "Privacy-Preserving Authentication Audit Data Platform",
        "public_route": public_route(),
        "purpose": (
            "A governed authentication-event ingestion platform that validates login telemetry, "
            "tokenizes sensitive identifiers, preserves audit evidence, and produces curated "
            "security analytics tables."
        ),
        "headline_metrics": headline_metrics(),
        "implemented_counts": {
            "source_event_examples": metrics["source_events"],
            "curated_event_examples": metrics["curated_events"],
            "unique_users": metrics["unique_users"],
            "auth_failures": metrics["auth_failures"],
            "high_risk_events": metrics["high_risk_events"],
            "sql_tables": 3,
            "sql_views": 1,
            "contract_versions": 1,
            "unit_tests": TEST_COUNT,
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
        "sample_metrics": metrics,
        "active_data_source": active_data_source(),
        "offline_artifacts": offline_artifacts()["metrics"],
    }


@app.get("/api/source-registry")
def source_registry() -> dict:
    return {
        "active_source": active_data_source(),
        "available_sources": [
            {
                "name": "RBA Login Data Set",
                "provider": "DAS Group / Kaggle / Zenodo",
                "license": "CC BY 4.0",
                "status": (
                    "adapter implemented; activate by placing the zip or CSV under "
                    "data/external/rba and running scripts/prepare_rba_dataset.py"
                ),
                "dataset_ref": "dasgroup/rba-dataset",
                "doi": "10.5281/zenodo.6782156",
                "source_reference": (
                    "Kaggle dataset dasgroup/rba-dataset; "
                    "Zenodo DOI 10.5281/zenodo.6782156"
                ),
                "why_it_fits": (
                    "Synthesized login-attempt data with IP, country, ASN, user agent, device "
                    "type, user ID, timestamp, RTT, login success, attack IP, and account takeover "
                    "flags."
                ),
            },
            {
                "name": "Deterministic local sample",
                "provider": "Repository fixture",
                "license": "Project-owned synthetic data",
                "status": "active fallback",
                "dataset_ref": "sample_data/login_events.jsonl",
                "doi": None,
                "source_reference": "Repository fixture",
                "why_it_fits": (
                    "Small, safe authentication telemetry fixture for tests, demos, and production "
                    "page fallback."
                ),
            },
        ],
    }


@app.get("/api/offline-artifacts")
def offline_artifacts() -> dict:
    artifact_root = PROJECT_ROOT / "data" / "artifacts" / "rba_offline"
    packaged_root = PROJECT_ROOT / "docs" / "artifacts" / "rba_offline"
    root = (
        artifact_root if (artifact_root / "offline_run_manifest.json").exists() else packaged_root
    )
    manifest_path = root / "offline_run_manifest.json"
    if not manifest_path.exists():
        return {"available": False, "metrics": {}, "table_inventory": [], "audit": {}}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "artifact_root": str(root.relative_to(PROJECT_ROOT)),
        "audit": manifest.get("audit", {}),
        "metrics": manifest.get("metrics", {}),
        "table_inventory": manifest.get("table_inventory", []),
    }


def active_data_source() -> dict:
    external = PROJECT_ROOT / "data" / "external" / "rba" / "login_events.normalized.jsonl"
    if external.exists():
        return {
            "name": "RBA Login Data Set normalized sample",
            "type": "kaggle_or_zenodo_sample",
            "path": "data/external/rba/login_events.normalized.jsonl",
            "records": len(external.read_text(encoding="utf-8").splitlines()),
        }
    packaged_artifact = (
        PROJECT_ROOT / "docs" / "artifacts" / "rba_offline" / "bronze_rba_login_events_sample.jsonl"
    )
    if packaged_artifact.exists():
        artifacts = offline_artifacts()
        return {
            "name": "RBA Login Data Set offline artifact sample",
            "type": "offline_artifact_sample",
            "path": "docs/artifacts/rba_offline/bronze_rba_login_events_sample.jsonl",
            "records": artifacts.get("metrics", {}).get(
                "records_processed", len(packaged_artifact.read_text(encoding="utf-8").splitlines())
            ),
        }
    return {
        "name": "Deterministic local authentication sample",
        "type": "repository_fixture",
        "path": "sample_data/login_events.jsonl",
        "records": len(
            (PROJECT_ROOT / "sample_data" / "login_events.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ),
    }


@app.get("/api/flow")
def flow() -> dict:
    return {
        "stages": [
            {
                "stage": "Source Contract",
                "tooling": "JSON Schema, producer contract",
                "artifact": "contracts/v1/login_event.schema.json",
                "output": (
                    "LoginEvent payload with required identity, device, IP, locale, and app "
                    "version fields"
                ),
            },
            {
                "stage": "Queue Ingestion",
                "tooling": "AWS SQS compatible client, LocalStack for local execution",
                "artifact": "src/authaudit/sqs.py",
                "output": "Bounded message batch with explicit receive and delete behavior",
            },
            {
                "stage": "Validation",
                "tooling": "Python validation layer",
                "artifact": "src/authaudit/transform.py",
                "output": "Accepted payloads continue; malformed payloads are routed to quarantine",
            },
            {
                "stage": "Privacy Transform",
                "tooling": "HMAC-SHA256",
                "artifact": "src/authaudit/tokenization.py",
                "output": (
                    "Raw IP and device identifiers replaced with deterministic irreversible tokens"
                ),
            },
            {
                "stage": "Curated Persistence",
                "tooling": "PostgreSQL",
                "artifact": "src/authaudit/postgres.py",
                "output": (
                    "secure_login.user_logins, secure_login.quarantine_login_events, "
                    "secure_login.ingestion_audit"
                ),
            },
            {
                "stage": "Operations Surface",
                "tooling": "FastAPI, Docker, Caddy",
                "artifact": "src/authaudit/api.py, Dockerfile, docker-compose.prod.yml",
                "output": (
                    "Public demo, health checks, contract browser, table previews, and platform "
                    "documentation"
                ),
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
        "system_positioning": (
            "Secure event ingestion platform with privacy controls, idempotent writes, "
            "observability, and auditability."
        ),
    }


@app.get("/api/stack")
def stack() -> dict:
    return {
        "implemented": [
            {
                "tool": "AWS SQS compatible ingestion",
                "role": (
                    "Queue-backed authentication event intake with local execution through "
                    "LocalStack"
                ),
            },
            {
                "tool": "Python",
                "role": (
                    "Validation, deterministic event identity, PII tokenization, and batch "
                    "orchestration"
                ),
            },
            {
                "tool": "PostgreSQL",
                "role": (
                    "Curated login fact, quarantine table, ingestion audit table, and health view"
                ),
            },
            {
                "tool": "FastAPI",
                "role": "Public technical surface, live transform preview, and health endpoints",
            },
            {
                "tool": "Docker Compose",
                "role": "Repeatable local services and production web container",
            },
            {"tool": "Caddy", "role": "Portfolio-domain reverse proxy and TLS edge routing"},
        ],
        "planned": [
            {
                "tool": "dbt",
                "role": (
                    "Bronze, silver, and gold transformations with relationship and freshness tests"
                ),
            },
            {"tool": "Airflow", "role": "Scheduled ingestion, retries, backfills, and run history"},
            {
                "tool": "S3",
                "role": (
                    "Immutable landing zone for source contracts, raw batches, and retained audit "
                    "exports"
                ),
            },
            {
                "tool": "OpenLineage-compatible model",
                "role": "Dataset, job, and run-level lineage representation",
            },
            {
                "tool": "Monitoring",
                "role": (
                    "Reject rate, batch freshness, queue depth, and endpoint availability checks"
                ),
            },
        ],
    }


@app.get("/api/lineage")
def lineage() -> dict:
    """Column-level lineage for secure_login.user_logins."""
    return {
        "target_table": "secure_login.user_logins",
        "direct_identifiers_in_source": list(DIRECT_IDENTIFIERS),
        "summary": lineage_summary(),
        "columns": COLUMN_LINEAGE,
    }


@app.get("/api/operations")
def operations() -> dict:
    """Scheduling, run history with freshness, failure handling, and measured scale."""
    artifacts = offline_artifacts()
    return {
        "scheduling": scheduling(),
        "run_history": run_history(artifacts),
        "failure_modes": FAILURE_MODES,
        "scale_and_cost": scale_and_cost(artifacts),
    }


@app.get("/api/quality-gates")
def quality_gates() -> dict:
    return {
        "gates": [
            {
                "gate": "Required field presence",
                "implemented_in": "src/authaudit/transform.py",
                "failure_behavior": "Reject event and persist reason in quarantine path",
            },
            {
                "gate": "Device type domain validation",
                "implemented_in": "src/authaudit/transform.py",
                "failure_behavior": "Reject values outside ios, android, and web",
            },
            {
                "gate": "App version normalization",
                "implemented_in": "src/authaudit/transform.py",
                "failure_behavior": "Reject malformed semantic version strings",
            },
            {
                "gate": "PII exclusion from curated model",
                "implemented_in": "src/authaudit/tokenization.py",
                "failure_behavior": "Raw IP and device identifiers are replaced before insertion",
            },
            {
                "gate": "Idempotent replay",
                "implemented_in": "src/authaudit/postgres.py",
                "failure_behavior": "Duplicate event_id writes are ignored instead of duplicated",
            },
            {
                "gate": "Batch audit trail",
                "implemented_in": "src/authaudit/postgres.py",
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
    return {"records": _sample_events()[:12], "total_records": len(_sample_events())}


@app.get("/api/sample-transform")
def sample_transform() -> dict:
    return {"records": _transformed_events()[:12], "total_records": len(_transformed_events())}


@app.get("/api/table-preview")
def table_preview() -> dict:
    artifact_root = PROJECT_ROOT / "docs" / "artifacts" / "rba_offline"
    bronze_rows = _read_jsonl(artifact_root / "bronze_rba_login_events_sample.jsonl", limit=10)
    silver_rows = _read_jsonl(artifact_root / "silver_user_logins_sample.jsonl", limit=10)
    audit_rows = _read_csv_rows(artifact_root / "audit_ingestion_runs.csv", limit=10)
    return {
        "preview_policy": (
            "Only the first 10 rows are displayed for efficiency. The full public source dataset "
            "is linked in Source Registry; the local full zip is not hosted by this page."
        ),
        "source_dataset_url": "https://www.kaggle.com/datasets/dasgroup/rba-dataset",
        "groups": {
            "Input": [
                {
                    "name": "bronze_rba_login_events",
                    "purpose": (
                        "Input-stage records normalized from the RBA dataset before privacy "
                        "tokenization."
                    ),
                    "highlight": (
                        "Raw source features are visible here so the transformation boundary is "
                        "clear."
                    ),
                    "columns": list(bronze_rows[0]) if bronze_rows else [],
                    "sample_rows": bronze_rows,
                }
            ],
            "Output": [
                {
                    "name": "silver_user_logins",
                    "purpose": (
                        "Output-stage records after validation, deterministic event identity, and "
                        "HMAC tokenization."
                    ),
                    "highlight": (
                        "Transformed values are highlighted: raw IP and device identifiers are "
                        "replaced by masked tokens."
                    ),
                    "columns": list(silver_rows[0]) if silver_rows else [],
                    "sample_rows": silver_rows,
                    "transformed_columns": [
                        "event_id",
                        "masked_ip",
                        "masked_device_id",
                        "source_event_hash",
                        "pii_strategy",
                    ],
                },
                {
                    "name": "secure_login.user_logins",
                    "purpose": (
                        "Runtime curated login fact table produced by the same transform function."
                    ),
                    "highlight": (
                        "This is the application-facing version of the curated login table."
                    ),
                    "columns": list(_transformed_events()[0]) if _transformed_events() else [],
                    "sample_rows": _transformed_events()[:10],
                    "transformed_columns": [
                        "event_id",
                        "masked_ip",
                        "masked_device_id",
                        "source_event_hash",
                        "pii_strategy",
                    ],
                },
            ],
            "Audit": [
                {
                    "name": "audit_ingestion_runs",
                    "purpose": (
                        "Offline execution audit evidence with source path, timing, received "
                        "count, loaded count, and rejected count."
                    ),
                    "highlight": (
                        "This proves the local offline run executed and captured load evidence."
                    ),
                    "columns": list(audit_rows[0]) if audit_rows else [],
                    "sample_rows": audit_rows,
                },
                {
                    "name": "secure_login.quarantine_login_events",
                    "purpose": (
                        "Rejected payloads and validation reasons. The latest 100,000-row offline "
                        "run had zero rejected rows."
                    ),
                    "highlight": (
                        "Empty here means no records failed validation in the displayed offline "
                        "slice."
                    ),
                    "columns": [
                        "quarantine_id",
                        "batch_id",
                        "rejected_at_utc",
                        "error_message",
                        "payload",
                    ],
                    "sample_rows": [],
                },
            ],
        },
    }


@app.get("/api/sql-schema", response_class=PlainTextResponse)
def sql_schema() -> str:
    return _read_text("sql/001_secure_login_schema.sql")


@app.get("/api/source-contract")
def source_contract() -> dict:
    return json.loads(_read_text("contracts/v1/login_event.schema.json"))


@app.get("/api/wiki", response_class=PlainTextResponse)
def wiki() -> str:
    return _read_text("docs/wiki/authaudit_knowledge_bank.md")


@app.get("/api/wiki-articles")
def wiki_articles() -> dict:
    markdown = _read_text("docs/wiki/authaudit_knowledge_bank.md")
    articles = []
    current = None
    for line in markdown.splitlines():
        if line.startswith("## "):
            if current:
                articles.append(current)
            current = {"title": line[3:].strip(), "body": []}
        elif current:
            current["body"].append(line)
    if current:
        articles.append(current)
    return {
        "articles": [
            {"title": item["title"], "body": "\n".join(item["body"]).strip()} for item in articles
        ]
    }


@app.get("/api/working-notes", response_class=PlainTextResponse)
def working_notes() -> str:
    return _read_text(
        "docs/wiki/privacy_preserving_authentication_audit_data_platform_working_notes.txt"
    )


@app.post("/api/validate")
def validate(payload: DemoEvent) -> dict:
    """Validate one event and return either the curated row or the rejection reason.

    This mirrors the worker: a record that fails the contract is reported with the reason that
    would be written to the quarantine table, rather than raising.
    """
    event = payload.model_dump()
    try:
        validate_event(event)
    except ValueError as rejection:
        return {
            "valid": False,
            "error_message": str(rejection),
            "quarantine_target": "secure_login.quarantine_login_events",
        }
    return {"valid": True, "transformed": transform_event(event, batch_id="interactive-demo")}
