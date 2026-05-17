import csv
import json
import zipfile
from pathlib import Path
from typing import Iterable


RBA_COLUMNS = {
    "ip_address": ["IP Address", "ip", "ip_address"],
    "country": ["Country", "country"],
    "region": ["Region", "region"],
    "city": ["City", "city"],
    "asn": ["ASN", "asn"],
    "user_agent": ["User Agent String", "user_agent", "user_agent_string"],
    "os": ["OS Name and Version", "os", "os_name_and_version"],
    "browser": ["Browser Name and Version", "browser", "browser_name_and_version"],
    "device_type": ["Device Type", "device_type"],
    "user_id": ["User ID", "user_id"],
    "login_timestamp": ["Login Timestamp", "login_timestamp"],
    "rtt_ms": ["Round-Trip Time (RTT) [ms]", "Round-Trip Time [ms]", "rtt_ms"],
    "login_successful": ["Login Successful", "login_successful"],
    "is_attack_ip": ["Is Attack IP", "is_attack_ip"],
    "is_account_takeover": ["Is Account Takeover", "is_account_takeover"],
}


def _first_present(row: dict[str, str], candidates: list[str], default: str = "") -> str:
    for key in candidates:
        if key in row and str(row[key]).strip() != "":
            return str(row[key]).strip()
    return default


def _bool_text(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _map_device_type(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"mobile", "tablet"}:
        return "android"
    if normalized in {"desktop", "bot", "unknown", ""}:
        return "web"
    if normalized in {"ios", "android", "web"}:
        return normalized
    return "web"


def _risk_band(login_successful: bool, is_attack_ip: bool, is_account_takeover: bool) -> str:
    if is_account_takeover or is_attack_ip:
        return "high"
    if not login_successful:
        return "medium"
    return "low"


def normalize_rba_row(row: dict[str, str]) -> dict[str, str]:
    login_successful = _bool_text(_first_present(row, RBA_COLUMNS["login_successful"], "true"))
    is_attack_ip = _bool_text(_first_present(row, RBA_COLUMNS["is_attack_ip"], "false"))
    is_account_takeover = _bool_text(_first_present(row, RBA_COLUMNS["is_account_takeover"], "false"))
    user_id = _first_present(row, RBA_COLUMNS["user_id"], "unknown_user")
    device_type = _map_device_type(_first_present(row, RBA_COLUMNS["device_type"], "web"))
    raw_timestamp = _first_present(row, RBA_COLUMNS["login_timestamp"], "")
    return {
        "user_id": f"rba_user_{user_id}",
        "device_type": device_type,
        "device_id": f"{device_type}:{_first_present(row, RBA_COLUMNS['browser'], 'browser_unknown')}:{_first_present(row, RBA_COLUMNS['os'], 'os_unknown')}",
        "ip": _first_present(row, RBA_COLUMNS["ip_address"], "0.0.0.0"),
        "locale": _first_present(row, RBA_COLUMNS["country"], "unknown"),
        "app_version": "1.0.0",
        "event_time_utc": raw_timestamp or "source_timestamp_unavailable",
        "auth_result": "success" if login_successful else "failure",
        "risk_band": _risk_band(login_successful, is_attack_ip, is_account_takeover),
        "country": _first_present(row, RBA_COLUMNS["country"], "unknown"),
        "region": _first_present(row, RBA_COLUMNS["region"], "unknown"),
        "city": _first_present(row, RBA_COLUMNS["city"], "unknown"),
        "asn": _first_present(row, RBA_COLUMNS["asn"], "unknown"),
        "rtt_ms": _first_present(row, RBA_COLUMNS["rtt_ms"], "unknown"),
        "source_system": "rba_dataset",
    }


def _iter_csv_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def _iter_zip_csv_rows(path: Path) -> Iterable[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError(f"No CSV file found inside {path}")
        with archive.open(csv_names[0]) as raw:
            text = (line.decode("utf-8-sig") for line in raw)
            yield from csv.DictReader(text)


def iter_rba_rows(path: Path, limit: int | None = None) -> Iterable[dict[str, str]]:
    iterator = _iter_zip_csv_rows(path) if path.suffix.lower() == ".zip" else _iter_csv_rows(path)
    for index, row in enumerate(iterator):
        if limit is not None and index >= limit:
            break
        yield normalize_rba_row(row)


def write_normalized_sample(source_path: Path, output_path: Path, limit: int = 5000) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in iter_rba_rows(source_path, limit=limit):
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
            count += 1
    return count
