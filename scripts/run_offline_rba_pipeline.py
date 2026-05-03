import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pramanaledger.sources import iter_rba_rows
from pramanaledger.transform import transform_event


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, default=str, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(source: Path, artifacts_dir: Path, limit: int, preview_rows: int) -> dict:
    started = datetime.now(timezone.utc)
    normalized_rows: list[dict] = []
    curated_rows: list[dict] = []
    device_counts: Counter[str] = Counter()
    country_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    auth_counts: Counter[str] = Counter()
    rtt_values: list[int] = []
    users: set[str] = set()

    for row in iter_rba_rows(source, limit=limit):
        normalized_rows.append(row)
        curated = transform_event(row, batch_id="offline-rba-local")
        curated_rows.append(curated)
        device_counts[curated["device_type"]] += 1
        risk_counts[curated["risk_band"]] += 1
        auth_counts[curated["auth_result"]] += 1
        country_counts[row.get("country", "unknown")] += 1
        users.add(curated["user_id"])
        try:
            rtt_values.append(int(str(row.get("rtt_ms", "")).strip()))
        except ValueError:
            pass

    completed = datetime.now(timezone.utc)
    audit = {
        "batch_id": "offline-rba-local",
        "source_path": str(source),
        "started_at_utc": started.isoformat(),
        "completed_at_utc": completed.isoformat(),
        "execution_seconds": round((completed - started).total_seconds(), 3),
        "messages_received": len(normalized_rows),
        "records_loaded": len(curated_rows),
        "records_rejected": 0,
    }
    metrics = {
        "dataset_name": "Login Data Set for Risk-Based Authentication",
        "dataset_doi": "10.5281/zenodo.6782156",
        "dataset_license": "CC BY 4.0",
        "records_processed": len(curated_rows),
        "unique_users": len(users),
        "auth_result_counts": dict(auth_counts),
        "risk_band_counts": dict(risk_counts),
        "device_type_counts": dict(device_counts),
        "top_countries": dict(country_counts.most_common(12)),
        "rtt_observed_count": len(rtt_values),
        "rtt_missing_count": len(curated_rows) - len(rtt_values),
        "average_rtt_ms": round(mean(rtt_values), 2) if rtt_values else None,
        "artifact_generated_at_utc": completed.isoformat(),
    }
    table_inventory = [
        {
            "table": "bronze_rba_login_events",
            "records": len(normalized_rows),
            "artifact": "bronze_rba_login_events_sample.jsonl",
            "purpose": "Normalized source contract records derived from the RBA dataset.",
        },
        {
            "table": "silver_user_logins",
            "records": len(curated_rows),
            "artifact": "silver_user_logins_sample.jsonl",
            "purpose": "Curated authentication records after validation and HMAC tokenization.",
        },
        {
            "table": "audit_ingestion_runs",
            "records": 1,
            "artifact": "audit_ingestion_runs.csv",
            "purpose": "Offline run audit evidence with record counts and execution timing.",
        },
    ]

    _write_jsonl(artifacts_dir / "bronze_rba_login_events_sample.jsonl", normalized_rows[:preview_rows])
    _write_jsonl(artifacts_dir / "silver_user_logins_sample.jsonl", curated_rows[:preview_rows])
    _write_csv(artifacts_dir / "audit_ingestion_runs.csv", [audit])
    _write_json(artifacts_dir / "offline_run_metrics.json", metrics)
    _write_json(artifacts_dir / "table_inventory.json", table_inventory)
    _write_json(artifacts_dir / "offline_run_manifest.json", {"audit": audit, "metrics": metrics, "table_inventory": table_inventory})
    return {"audit": audit, "metrics": metrics, "table_inventory": table_inventory}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Privacy-Preserving Authentication Audit Data Platform RBA pipeline entirely offline and capture artifacts.")
    parser.add_argument("--source", default="data/external/rba/rba-dataset.zip")
    parser.add_argument("--artifacts-dir", default="data/artifacts/rba_offline")
    parser.add_argument("--limit", type=int, default=100000)
    parser.add_argument("--preview-rows", type=int, default=1000)
    args = parser.parse_args()

    result = run(Path(args.source), Path(args.artifacts_dir), limit=args.limit, preview_rows=args.preview_rows)
    print(json.dumps(result["audit"], indent=2))
    print(json.dumps(result["metrics"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
