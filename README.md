## Project #8 – Login Events ETL (SQS → Postgres with Hash Masking)

Short description:  
Python ETL that consumes login events from an AWS SQS queue (via LocalStack), pseudonymizes sensitive fields with SHA-256 hashing, and loads them into a Postgres `user_logins` table.

---

### Problem / Use-case

Product teams need a secure way to analyze login patterns without storing raw IP addresses or device IDs.  
This script builds a tiny end-to-end pipeline:

- **Source:** SQS queue with JSON login events.
- **Transform:** Mask sensitive identifiers using one-way hashing.
- **Target:** PostgreSQL table with analytics-friendly schema.

---

### Tech Stack

- **Python** – core ETL logic
- **boto3** – read messages from SQS (LocalStack endpoint)
- **hashlib** – SHA-256 hash for masking `device_id` and `ip`
- **psycopg2** – connect and write to PostgreSQL
- **PostgreSQL** – destination warehouse table
- **LocalStack + Docker** – local emulation of SQS and Postgres

---

### Data Flow

1. Connect to **LocalStack SQS** at `http://localhost:4566`.
2. Read messages from `login-queue`.
3. For each JSON message:
   - Parse `user_id`, `device_type`, `device_id`, `ip`, `locale`, `app_version`.
   - Hash `device_id` and `ip` with SHA-256 to produce:
     - `masked_device_id`
     - `masked_ip`
   - Convert `app_version` like `"5.2.3"` → major version integer `5`.
4. Connect to **PostgreSQL** on `localhost:5432`.
5. Ensure target table exists (`CREATE TABLE IF NOT EXISTS user_logins (...)`).
6. Insert a row into `user_logins` with:
   - `user_id`
   - `device_type`
   - `masked_ip`
   - `masked_device_id`
   - `locale`
   - `app_version` (int)
   - `create_date` (current timestamp)
7. Commit and close the DB connection.

---

### Target Table Schema

`user_logins` (PostgreSQL)

| Column            | Type          | Description                                   |
|-------------------|---------------|-----------------------------------------------|
| `user_id`         | varchar(128)  | Logical user identifier                       |
| `device_type`     | varchar(32)   | Device category (e.g. `ios`, `android`)      |
| `masked_ip`       | varchar(256)  | SHA-256 hash of raw IP                        |
| `masked_device_id`| varchar(256)  | SHA-256 hash of raw device ID                 |
| `locale`          | varchar(32)   | User locale (e.g. `en_US`)                    |
| `app_version`     | integer       | Major app version number                      |
| `create_date`     | date          | Ingestion timestamp                           |

---

### Security / Privacy Notes

- **One-way hashing:** `hashlib.sha256` is used so raw IPs and device IDs are never stored.
- **Uniqueness preserved:** hashed values remain stable and unique per device/IP, enabling:
  - device-level session analysis
  - IP-based anomaly detection
  - repeat-login analytics  
  without storing any clear-text identifiers.

---

### How to Run Locally

1. **Start LocalStack and Postgres** (e.g. via Docker Compose) exposing:
   - SQS on `http://localhost:4566`
   - Postgres on `localhost:5432`
2. **Create the SQS queue** in LocalStack:
   - `login-queue` (matching the `QueueUrl` in the script).
3. **Send test login events** as SQS messages with a JSON body like:

   ```json
   {
     "user_id": "user_123",
     "device_type": "android",
     "device_id": "A1B2C3D4",
     "ip": "192.168.1.10",
     "locale": "en_US",
     "app_version": "5.2.3"
   }
