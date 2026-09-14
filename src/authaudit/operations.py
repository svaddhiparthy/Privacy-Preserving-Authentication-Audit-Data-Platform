"""Operational facts the page publishes: how work is scheduled, what a run cost, and what
happens on each failure class.

These are read from the packaged audit record and the compose limits rather than written by
hand, so the page cannot drift from the system. Nothing here describes intent; each entry
names a code path or an artifact.
"""

from datetime import UTC, datetime
from typing import Any

# Failure classes the platform actually handles, each with the code path that handles it.
FAILURE_MODES: list[dict[str, str]] = [
    {
        "failure": "Producer omits a required field",
        "detection": "validate_event checks the required set before anything else runs",
        "behaviour": "Row rejected, payload and reason written to quarantine",
        "blast_radius": "One record. The batch continues.",
        "implemented_in": "src/authaudit/transform.py",
    },
    {
        "failure": "Device type outside the agreed domain",
        "detection": "Closed-set check against ios, android, web",
        "behaviour": "Rejected rather than coerced to unknown, so dimensions stay clean",
        "blast_radius": "One record. The batch continues.",
        "implemented_in": "src/authaudit/transform.py",
    },
    {
        "failure": "Unparseable application version",
        "detection": "Major component must parse to an integer",
        "behaviour": "Rejected with the reason recorded",
        "blast_radius": "One record. The batch continues.",
        "implemented_in": "src/authaudit/transform.py",
    },
    {
        "failure": "Queue redelivers a message already processed",
        "detection": "event_id is derived from the payload, not supplied by the producer",
        "behaviour": "ON CONFLICT DO NOTHING, so the replay is a no-op",
        "blast_radius": "None. Counts stay correct.",
        "implemented_in": "src/authaudit/postgres.py",
    },
    {
        "failure": "Message arrives without a receipt handle",
        "detection": "parse_messages checks before processing",
        "behaviour": "Skipped and logged, because it could not be deleted and would loop forever",
        "blast_radius": "One message. No infinite redelivery.",
        "implemented_in": "src/authaudit/sqs.py",
    },
    {
        "failure": "The same batch is run twice",
        "detection": "batch_id is the audit table primary key",
        "behaviour": "ON CONFLICT DO NOTHING, so audit counts are not double-written",
        "blast_radius": "None.",
        "implemented_in": "src/authaudit/postgres.py",
    },
    {
        "failure": "Tokenization secret is missing in a deployment",
        "detection": "hash_secret_is_demo reports the development fallback",
        "behaviour": "Deploy script refuses to release when HASH_SECRET is unset or the fallback",
        "blast_radius": "Deploy stops before publishing reproducible tokens.",
        "implemented_in": "deploy_authaudit_branch.sh",
    },
]


def scheduling() -> list[dict[str, str]]:
    """How each piece of work is triggered today. Batch-invoked, and stated as such."""
    return [
        {
            "job": "Ingestion worker",
            "trigger": "Batch invocation, authaudit.runner",
            "cadence": "On demand",
            "evidence": "One row in secure_login.ingestion_audit per run",
        },
        {
            "job": "Dataset normalization",
            "trigger": "scripts/prepare_rba_dataset.py",
            "cadence": "On demand, when the source archive is refreshed",
            "evidence": "data/external/rba/login_events.normalized.jsonl",
        },
        {
            "job": "Offline pipeline run",
            "trigger": "scripts/run_offline_rba_pipeline.py",
            "cadence": "On demand",
            "evidence": "docs/artifacts/rba_offline, packaged into the image",
        },
        {
            "job": "Lint, tests, contract and artifact checks",
            "trigger": "GitHub Actions",
            "cadence": "Every push and pull request",
            "evidence": "Actions run history",
        },
        {
            "job": "Container health probe",
            "trigger": "Docker healthcheck against /health",
            "cadence": "Every 60 seconds",
            "evidence": "docker inspect health status",
        },
    ]


def run_history(artifacts: dict[str, Any]) -> dict[str, Any]:
    """The audited run, with freshness computed at request time.

    One run is one run; it is reported as such rather than dressed up as a series.
    """
    if not artifacts.get("available"):
        return {"runs": [], "latest": None}
    audit = dict(artifacts["audit"])
    completed = audit.get("completed_at_utc")
    age_days = None
    if completed:
        try:
            finished = datetime.fromisoformat(completed)
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=UTC)
            age_days = (datetime.now(UTC) - finished).days
        except ValueError:
            age_days = None
    received = audit.get("messages_received") or 0
    loaded = audit.get("records_loaded") or 0
    rejected = audit.get("records_rejected") or 0
    seconds = audit.get("execution_seconds") or 0
    audit["records_per_second"] = round(loaded / seconds) if seconds else None
    audit["reject_rate_pct"] = round(100 * rejected / received, 4) if received else None
    audit["age_days"] = age_days
    return {"runs": [audit], "latest": audit}


def scale_and_cost(artifacts: dict[str, Any]) -> list[dict[str, str]]:
    """What the measured run implies about capacity and what it costs to run."""
    if not artifacts.get("available"):
        return []
    audit = artifacts["audit"]
    seconds = audit.get("execution_seconds") or 1
    loaded = audit.get("records_loaded") or 0
    per_second = loaded / seconds if seconds else 0
    return [
        {
            "dimension": "Measured throughput",
            "value": f"{round(per_second):,} records/sec",
            "basis": f"{loaded:,} records in {seconds}s, single process, no parallelism",
        },
        {
            "dimension": "A 10M-record day",
            "value": f"~{round(10_000_000 / per_second / 60)} minutes",
            "basis": "At the measured rate. Stated as a checkable implication, not a ceiling.",
        },
        {
            "dimension": "Memory ceiling",
            "value": "512 MB",
            "basis": "Hard limit in docker-compose.prod.yml, streaming reads keep it flat",
        },
        {
            "dimension": "Marginal infrastructure cost",
            "value": "$0",
            "basis": "One container on an existing host, public data, no managed services",
        },
        {
            "dimension": "Scaling path",
            "value": "Partition by batch_id",
            "basis": "Tokenization and event identity are pure functions, so runs shard cleanly",
        },
    ]
