"""Public surface smoke tests: the endpoints the project page depends on."""

import unittest

from fastapi.testclient import TestClient

from authaudit.api import TEST_COUNT, app

client = TestClient(app)


class HealthTests(unittest.TestCase):
    def test_healthz_reports_the_service_name(self) -> None:
        response = client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertIn("authaudit", response.json()["service"])

    def test_health_alias_matches(self) -> None:
        self.assertEqual(client.get("/health").json(), client.get("/healthz").json())


class ContractTests(unittest.TestCase):
    def test_source_contract_is_served(self) -> None:
        payload = client.get("/api/source-contract").json()
        self.assertEqual(payload["title"], "LoginEvent")
        self.assertIn("user_id", payload["required"])

    def test_sql_schema_is_served(self) -> None:
        body = client.get("/api/sql-schema").text
        self.assertIn("CREATE SCHEMA IF NOT EXISTS secure_login", body)
        self.assertIn("quarantine_login_events", body)


class TransformPreviewTests(unittest.TestCase):
    def test_sample_transform_returns_tokenized_rows(self) -> None:
        records = client.get("/api/sample-transform").json()["records"]
        self.assertTrue(records)
        row = records[0]
        self.assertIn("masked_ip", row)
        self.assertNotIn("ip", row)
        self.assertNotIn("device_id", row)
        self.assertEqual(len(row["masked_ip"]), 64)

    def test_source_and_curated_row_counts_match(self) -> None:
        source = client.get("/api/sample-events").json()["records"]
        curated = client.get("/api/sample-transform").json()["records"]
        self.assertEqual(len(source), len(curated))

    def test_validate_accepts_a_good_event(self) -> None:
        response = client.post(
            "/api/validate",
            json={
                "user_id": "user_123",
                "device_type": "android",
                "device_id": "A1B2C3D4",
                "ip": "192.168.1.10",
                "locale": "en_US",
                "app_version": "5.2.3",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])

    def test_validate_rejects_a_bad_device_type(self) -> None:
        response = client.post(
            "/api/validate",
            json={
                "user_id": "user_123",
                "device_type": "smart-fridge",
                "device_id": "A1B2C3D4",
                "ip": "192.168.1.10",
                "locale": "en_US",
                "app_version": "5.2.3",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["valid"])
        self.assertIn("device_type", body["error_message"])
        self.assertEqual(body["quarantine_target"], "secure_login.quarantine_login_events")


class EvidenceTests(unittest.TestCase):
    def test_offline_artifacts_are_packaged(self) -> None:
        payload = client.get("/api/offline-artifacts").json()
        self.assertTrue(payload["available"])
        self.assertEqual(payload["audit"]["records_loaded"], 100000)

    def test_audit_evidence_carries_no_operator_filesystem_path(self) -> None:
        """Published audit evidence must not leak the machine it was produced on."""
        payload = client.get("/api/offline-artifacts").json()
        source_path = payload["audit"]["source_path"]
        self.assertNotIn(chr(92), source_path)
        self.assertFalse(source_path.startswith("/"))
        self.assertNotIn(":", source_path)

    def test_quality_gates_reference_real_modules(self) -> None:
        gates = client.get("/api/quality-gates").json()
        entries = gates if isinstance(gates, list) else gates.get("gates", [])
        self.assertTrue(entries)
        for gate in entries:
            with self.subTest(gate=gate.get("gate")):
                self.assertIn("src/authaudit/", gate["implemented_in"])


if __name__ == "__main__":
    unittest.main()


class HeadlineMetricsTests(unittest.TestCase):
    """The hero must lead with the audited run, not the demo fixture."""

    def setUp(self) -> None:
        self.metrics = client.get("/api/platform-summary").json()["headline_metrics"]

    def test_six_headline_metrics_are_published(self) -> None:
        self.assertEqual(len(self.metrics), 6)
        for m in self.metrics:
            with self.subTest(m=m):
                self.assertTrue(m["value"])
                self.assertTrue(m["label"])

    def test_leads_with_the_full_run_volume(self) -> None:
        self.assertEqual(self.metrics[0]["value"], "100,000")

    def test_reports_throughput_and_a_clean_contract_pass(self) -> None:
        self.assertIn("k/s", self.metrics[1]["value"])
        self.assertEqual(self.metrics[2]["value"], "100.0%")

    def test_test_count_matches_the_suite(self) -> None:
        counts = client.get("/api/platform-summary").json()["implemented_counts"]
        self.assertEqual(counts["unit_tests"], TEST_COUNT)


class OperationsEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ops = client.get("/api/operations").json()

    def test_publishes_scheduling_failures_and_scale(self) -> None:
        self.assertTrue(self.ops["scheduling"])
        self.assertTrue(self.ops["failure_modes"])
        self.assertTrue(self.ops["scale_and_cost"])

    def test_run_history_reports_the_audited_run(self) -> None:
        latest = self.ops["run_history"]["latest"]
        self.assertEqual(latest["records_loaded"], 100000)
        self.assertEqual(latest["records_rejected"], 0)
        self.assertGreater(latest["records_per_second"], 0)


class LineageEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lineage = client.get("/api/lineage").json()

    def test_targets_the_curated_table(self) -> None:
        self.assertEqual(self.lineage["target_table"], "secure_login.user_logins")

    def test_no_direct_identifier_is_stored_raw(self) -> None:
        for column in self.lineage["columns"]:
            if column["kind"] != "carried":
                continue
            with self.subTest(column=column["column"]):
                for identifier in self.lineage["direct_identifiers_in_source"]:
                    self.assertNotIn(identifier, column["sources"])
