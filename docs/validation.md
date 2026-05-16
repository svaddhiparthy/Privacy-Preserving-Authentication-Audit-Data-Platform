# Validation

The validation path covers code behavior, contract handling, and runtime import health.

## Commands

```powershell
python -m unittest discover -s tests -p "test_*.py"
Get-ChildItem src\pramanaledger\*.py | ForEach-Object { python -m py_compile $_.FullName }
python -m py_compile code_fetch_vaddhiparthy.py demo_api.py
powershell -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
```

## Ingestion Rules

`src/pramanaledger/transform.py` enforces:

- required authentication-event fields;
- non-blank `user_id`;
- allowed `device_type` values;
- allowed `auth_result` values when present;
- allowed `risk_band` values when present;
- parseable app-version major number.

Invalid records are rejected before curated persistence.

## Privacy Rules

The curated model must not persist raw IP or raw device identifiers. Those values are replaced with HMAC-SHA256 tokens before insertion into `secure_login.user_logins`.

## Audit Rules

Each batch writes:

- `messages_received`;
- `records_loaded`;
- `records_rejected`;
- `started_at_utc`;
- `completed_at_utc`.

These fields support replay checks, reject-rate review, and ingestion freshness review.
