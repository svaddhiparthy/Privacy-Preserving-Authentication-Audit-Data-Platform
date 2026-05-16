# Operations

This project is local-first. LocalStack and PostgreSQL are the expected development services.

## Local Services

```powershell
docker compose up -d
```

Create the SQS-compatible queue:

```powershell
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name login-queue
```

Run the worker:

```powershell
$env:PYTHONPATH = "src"
python code_fetch_vaddhiparthy.py
```

Run the API:

```powershell
uvicorn demo_api:app --reload --port 8075
```

## Health

- `GET /health`
- `GET /healthz`

Both endpoints return simple service health for local smoke checks or external monitors.

## Secret Handling

Use `.env.example` as the configuration template. Real `.env` files are ignored by Git.

Do not commit:

- real queue URLs for private environments;
- database passwords;
- HMAC secrets;
- raw production authentication logs;
- downloaded RBA source archives.

## Recovery

The ingestion path is replay-safe when the same source event and HMAC secret are used. Duplicate curated writes are controlled by the deterministic `event_id` primary key and PostgreSQL conflict handling.
