import json
from datetime import UTC, datetime
from typing import Any

from authaudit.config import resolve_hash_secret
from authaudit.tokenization import hash_value, hmac_value

REQUIRED_FIELDS = {
    "user_id",
    "device_type",
    "device_id",
    "ip",
    "locale",
    "app_version",
}


def canonical_event_hash(event: dict[str, Any]) -> str:
    return hash_value(json.dumps(event, sort_keys=True, separators=(",", ":")))


def parse_major_version(app_version: str) -> int:
    major = app_version.split(".", 1)[0]
    return int(major)


def validate_event(event: dict[str, Any]) -> None:
    missing_fields = sorted(REQUIRED_FIELDS - set(event))
    if missing_fields:
        raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
    if not str(event["user_id"]).strip():
        raise ValueError("user_id cannot be blank")
    if str(event["device_type"]).lower() not in {"ios", "android", "web"}:
        raise ValueError("device_type must be one of ios, android, web")
    if "auth_result" in event and str(event["auth_result"]).lower() not in {"success", "failure"}:
        raise ValueError("auth_result must be success or failure")
    if "risk_band" in event and str(event["risk_band"]).lower() not in {"low", "medium", "high"}:
        raise ValueError("risk_band must be low, medium, or high")
    parse_major_version(str(event["app_version"]))


def transform_event(
    event: dict[str, Any],
    ingested_at: datetime | None = None,
    *,
    hash_secret: str | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    """Validate an event and return its curated, tokenized row.

    ``hash_secret`` defaults to the HASH_SECRET environment variable, resolved per call so a
    deployment cannot be pinned to the development fallback by an import-time default.
    """
    validate_event(event)
    hash_secret = hash_secret if hash_secret is not None else resolve_hash_secret()
    timestamp = ingested_at or datetime.now(UTC)
    source_hash = canonical_event_hash(event)
    return {
        "event_id": hmac_value(source_hash, hash_secret),
        "batch_id": batch_id or "interactive",
        "user_id": str(event["user_id"]),
        "device_type": str(event["device_type"]).lower(),
        "masked_ip": hmac_value(str(event["ip"]), hash_secret),
        "masked_device_id": hmac_value(str(event["device_id"]), hash_secret),
        "locale": str(event["locale"]),
        "event_time_utc": str(event.get("event_time_utc", timestamp.isoformat())),
        "auth_result": str(event.get("auth_result", "success")).lower(),
        "risk_band": str(event.get("risk_band", "low")).lower(),
        "app_version": parse_major_version(str(event["app_version"])),
        "app_version_raw": str(event["app_version"]),
        "source_event_hash": source_hash,
        "pii_strategy": "hmac_sha256_secret_salted",
        "create_date": timestamp.date(),
        "ingested_at_utc": timestamp,
    }
