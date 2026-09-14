"""Persistence behaviour: idempotent replay, quarantine, and batch audit evidence.

These assert the SQL contract through a recording cursor rather than a live server, so the
suite stays runnable in CI without a database. The statements themselves are what carries
the replay-safety and audit guarantees, so they are what is asserted.
"""

import unittest
from datetime import UTC, datetime

from authaudit.postgres import (
    ensure_table_exists,
    insert_audit,
    insert_events,
    insert_quarantine,
)

SCHEMA = "secure_login"


class RecordingCursor:
    """Minimal stand-in that records the SQL and parameters it is handed."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, object]] = []

    def execute(self, sql, params=None) -> None:
        self.statements.append((" ".join(sql.split()), params))

    def executemany(self, sql, rows) -> None:
        self.statements.append((" ".join(sql.split()), list(rows)))

    @property
    def sql(self) -> str:
        return " | ".join(s for s, _ in self.statements)


def curated_row(event_id: str = "evt-1") -> dict:
    now = datetime(2026, 4, 23, tzinfo=UTC)
    return {
        "event_id": event_id,
        "batch_id": "batch-1",
        "user_id": "user_123",
        "device_type": "android",
        "masked_ip": "a" * 64,
        "masked_device_id": "b" * 64,
        "locale": "en_US",
        "event_time_utc": now.isoformat(),
        "auth_result": "success",
        "risk_band": "low",
        "app_version": 5,
        "app_version_raw": "5.2.3",
        "source_event_hash": "c" * 64,
        "pii_strategy": "hmac_sha256_secret_salted",
        "create_date": now.date(),
        "ingested_at_utc": now,
    }


class EnsureTableExistsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cursor = RecordingCursor()
        ensure_table_exists(self.cursor, SCHEMA)

    def test_creates_the_schema(self) -> None:
        self.assertIn(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}", self.cursor.sql)

    def test_creates_the_production_shaped_triad(self) -> None:
        for table in ("user_logins", "ingestion_audit", "quarantine_login_events"):
            with self.subTest(table=table):
                self.assertIn(f"CREATE TABLE IF NOT EXISTS {SCHEMA}.{table}", self.cursor.sql)

    def test_curated_table_is_keyed_on_event_id(self) -> None:
        self.assertIn("event_id varchar(128) PRIMARY KEY", self.cursor.sql)

    def test_every_statement_is_idempotent(self) -> None:
        for sql, _ in self.cursor.statements:
            with self.subTest(sql=sql[:40]):
                self.assertIn("IF NOT EXISTS", sql)


class InsertEventsTests(unittest.TestCase):
    def test_replay_is_ignored_rather_than_duplicated(self) -> None:
        cursor = RecordingCursor()
        insert_events(cursor, [curated_row()], SCHEMA)
        self.assertIn("ON CONFLICT (event_id) DO NOTHING", cursor.sql)

    def test_writes_into_the_curated_table(self) -> None:
        cursor = RecordingCursor()
        insert_events(cursor, [curated_row()], SCHEMA)
        self.assertIn(f"INSERT INTO {SCHEMA}.user_logins", cursor.sql)

    def test_passes_every_row_through(self) -> None:
        cursor = RecordingCursor()
        rows = [curated_row("evt-1"), curated_row("evt-2")]
        insert_events(cursor, rows, SCHEMA)
        self.assertEqual(cursor.statements[0][1], rows)

    def test_no_raw_identifier_column_is_written(self) -> None:
        cursor = RecordingCursor()
        insert_events(cursor, [curated_row()], SCHEMA)
        sql = cursor.sql
        self.assertIn("masked_ip", sql)
        self.assertIn("masked_device_id", sql)
        self.assertNotIn(" ip,", sql)
        self.assertNotIn("device_id,", sql.replace("masked_device_id,", ""))


class InsertQuarantineTests(unittest.TestCase):
    def test_writes_rejected_payloads_with_a_reason(self) -> None:
        cursor = RecordingCursor()
        cursor_rows = [
            {
                "batch_id": "batch-1",
                "rejected_at_utc": datetime.now(UTC),
                "error_message": "device_type must be one of ios, android, web",
                "payload": "{}",
            }
        ]
        insert_quarantine(cursor, "batch-1", cursor_rows, SCHEMA)
        self.assertIn(f"INSERT INTO {SCHEMA}.quarantine_login_events", cursor.sql)
        self.assertIn("error_message", cursor.sql)

    def test_is_a_no_op_when_nothing_was_rejected(self) -> None:
        cursor = RecordingCursor()
        insert_quarantine(cursor, "batch-1", [], SCHEMA)
        self.assertEqual(cursor.statements, [])


class InsertAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cursor = RecordingCursor()
        started = datetime(2026, 4, 23, 10, 0, tzinfo=UTC)
        completed = datetime(2026, 4, 23, 10, 5, tzinfo=UTC)
        insert_audit(
            self.cursor,
            schema=SCHEMA,
            batch_id="batch-1",
            started_at=started,
            completed_at=completed,
            messages_received=100,
            records_loaded=98,
            records_rejected=2,
        )

    def test_records_the_batch_counts(self) -> None:
        self.assertIn(f"INSERT INTO {SCHEMA}.ingestion_audit", self.cursor.sql)
        self.assertEqual(self.cursor.statements[0][1][4:], (98, 2))

    def test_audit_rows_are_idempotent_per_batch(self) -> None:
        self.assertIn("ON CONFLICT (batch_id) DO NOTHING", self.cursor.sql)


if __name__ == "__main__":
    unittest.main()
