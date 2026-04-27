import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "sample_data" / "login_events.jsonl"


def main() -> None:
    device_types = ["web", "ios", "android"]
    locales = ["en_US", "en_GB", "es_US", "fr_CA", "hi_IN"]
    networks = ["10.10.1.", "10.10.2.", "172.16.5.", "192.168.44.", "100.64.8."]
    users = [f"user_{1000 + i}" for i in range(30)]
    base = datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(120):
        user = users[i % len(users)]
        device_type = device_types[(i + (i // 9)) % len(device_types)]
        ip_octet = 10 + ((i * 7) % 220)
        app_major = 5 + (i % 4)
        app_minor = (i * 3) % 10
        app_patch = (i * 5) % 12
        event = {
            "user_id": user,
            "device_type": device_type,
            "device_id": f"{device_type.upper()}-{100000 + (i * 7919) % 899999}",
            "ip": f"{networks[i % len(networks)]}{ip_octet}",
            "locale": locales[(i * 2) % len(locales)],
            "app_version": f"{app_major}.{app_minor}.{app_patch}",
            "event_time_utc": (base + timedelta(minutes=i * 11)).isoformat(),
            "auth_result": "success" if i % 11 else "failure",
            "risk_band": ["low", "medium", "high"][(i + i // 13) % 3],
        }
        rows.append(json.dumps(event, separators=(",", ":")))
    OUTPUT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} events to {OUTPUT}")


if __name__ == "__main__":
    main()
