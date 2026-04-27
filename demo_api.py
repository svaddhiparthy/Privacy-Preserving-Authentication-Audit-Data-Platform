import json
import sys
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pramanaledger.transform import transform_event, validate_event


app = FastAPI(title="Secure Login Events Ingestion Demo")


class DemoEvent(BaseModel):
    user_id: str
    device_type: str
    device_id: str
    ip: str
    locale: str
    app_version: str


@app.get("/", response_class=HTMLResponse)
def demo_page() -> str:
    return Path("docs/demo.html").read_text(encoding="utf-8")


@app.get("/api/architecture")
def architecture() -> dict:
    return {
        "layers": [
            "SQS source queue",
            "bronze raw payload capture",
            "contract validation",
            "PII tokenization with HMAC-SHA256",
            "silver analytics model",
            "quarantine for rejected records",
            "batch audit and freshness metrics",
        ],
        "resume_positioning": "Secure event ingestion platform with privacy controls, idempotent writes, observability, and auditability.",
    }


@app.get("/api/stack")
def stack() -> dict:
    return {
        "current": [
            {"tool": "AWS SQS / LocalStack", "role": "Queue-backed event ingestion and local cloud emulation"},
            {"tool": "FastAPI", "role": "Interactive demo API and validation endpoint"},
            {"tool": "PostgreSQL", "role": "Relational serving store with secure_login schema"},
            {"tool": "HMAC-SHA256", "role": "Secret-salted irreversible PII tokenization"},
            {"tool": "SQL audit tables", "role": "Batch evidence, rejected-row tracking, and freshness reporting"},
            {"tool": "Docker Compose", "role": "Local reproducibility for queue and database infrastructure"},
        ],
        "next_level": [
            {"tool": "dbt", "role": "Bronze/silver/gold transformations and data tests"},
            {"tool": "Great Expectations", "role": "Contract validation, distribution checks, and quality reports"},
            {"tool": "Airflow or Dagster", "role": "Orchestration, retries, backfills, and dependency graph"},
            {"tool": "OpenLineage-compatible events", "role": "Dataset/job/run lineage model for pipeline observability"},
            {"tool": "Prometheus + Grafana", "role": "Ingestion lag, reject rate, throughput, and SLA dashboards"},
            {"tool": "Kafka-compatible mode", "role": "Streaming path for higher-volume telemetry ingestion"},
        ],
    }


@app.get("/api/quality-gates")
def quality_gates() -> dict:
    return {
        "gates": [
            "Required field presence",
            "Device type domain validation",
            "Semantic app version parsing",
            "PII never lands in curated tables",
            "Deterministic event_id supports replay without duplicates",
            "Malformed events go to quarantine instead of silently disappearing",
            "Every load writes an ingestion_audit row",
        ],
        "metrics": {
            "freshness_sla_minutes": 15,
            "max_reject_rate_percent": 2,
            "duplicate_handling": "ON CONFLICT DO NOTHING on event_id",
            "replay_mode": "safe because event_id is deterministic",
        },
    }


@app.get("/api/sample-transform")
def sample_transform() -> dict:
    rows = []
    for line in Path("sample_data/login_events.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        rows.append(transform_event(event, batch_id="demo-" + uuid4().hex[:8]))
    return {"records": rows}


@app.post("/api/validate")
def validate(payload: DemoEvent) -> dict:
    event = payload.model_dump()
    validate_event(event)
    return {"valid": True, "transformed": transform_event(event, batch_id="interactive-demo")}
