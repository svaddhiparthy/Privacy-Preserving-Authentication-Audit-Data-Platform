"""Operational facts published on the page must stay tied to the system."""

import unittest
from pathlib import Path

from authaudit.operations import FAILURE_MODES, run_history, scale_and_cost, scheduling

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ARTIFACTS = {
    "available": True,
    "audit": {
        "batch_id": "test-batch",
        "started_at_utc": "2026-01-01T00:00:00+00:00",
        "completed_at_utc": "2026-01-01T00:00:10+00:00",
        "execution_seconds": 10.0,
        "messages_received": 1000,
        "records_loaded": 1000,
        "records_rejected": 0,
    },
}


class FailureModeTests(unittest.TestCase):
    def test_every_failure_names_a_real_file(self) -> None:
        for mode in FAILURE_MODES:
            path = mode["implemented_in"]
            if path.endswith(".sh"):
                continue  # lives on the deploy host, not in the repo
            with self.subTest(failure=mode["failure"]):
                self.assertTrue((PROJECT_ROOT / path).exists(), f"missing: {path}")

    def test_every_failure_states_a_blast_radius(self) -> None:
        for mode in FAILURE_MODES:
            with self.subTest(failure=mode["failure"]):
                self.assertTrue(mode["blast_radius"].strip())
                self.assertTrue(mode["detection"].strip())
                self.assertTrue(mode["behaviour"].strip())


class SchedulingTests(unittest.TestCase):
    def test_each_job_declares_cadence_and_evidence(self) -> None:
        for job in scheduling():
            with self.subTest(job=job["job"]):
                self.assertTrue(job["cadence"].strip())
                self.assertTrue(job["evidence"].strip())


class RunHistoryTests(unittest.TestCase):
    def test_derives_throughput_and_reject_rate(self) -> None:
        latest = run_history(ARTIFACTS)["latest"]
        self.assertEqual(latest["records_per_second"], 100)
        self.assertEqual(latest["reject_rate_pct"], 0.0)

    def test_reports_age_in_days(self) -> None:
        self.assertIsInstance(run_history(ARTIFACTS)["latest"]["age_days"], int)

    def test_empty_when_no_artifacts(self) -> None:
        self.assertEqual(run_history({"available": False}), {"runs": [], "latest": None})


class ScaleAndCostTests(unittest.TestCase):
    def test_every_claim_states_its_basis(self) -> None:
        rows = scale_and_cost(ARTIFACTS)
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(dimension=row["dimension"]):
                self.assertTrue(row["basis"].strip())

    def test_throughput_is_derived_from_the_run(self) -> None:
        rows = {r["dimension"]: r["value"] for r in scale_and_cost(ARTIFACTS)}
        self.assertEqual(rows["Measured throughput"], "100 records/sec")


if __name__ == "__main__":
    unittest.main()
