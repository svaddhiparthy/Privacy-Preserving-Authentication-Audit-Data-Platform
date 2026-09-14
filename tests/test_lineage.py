"""Lineage is the auditable form of the privacy claim, so it is tested like one."""

import unittest
from datetime import UTC, datetime

from authaudit.lineage import COLUMN_LINEAGE, DIRECT_IDENTIFIERS, lineage_summary
from authaudit.transform import transform_event

VALID_EVENT = {
    "user_id": "user_123",
    "device_type": "android",
    "device_id": "A1B2C3D4",
    "ip": "192.168.1.10",
    "locale": "en_US",
    "app_version": "5.2.3",
}


class LineageCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.row = transform_event(
            dict(VALID_EVENT), datetime(2026, 4, 23, tzinfo=UTC), hash_secret="unit-test-secret"
        )

    def test_lineage_covers_every_curated_column_exactly_once(self) -> None:
        documented = [c["column"] for c in COLUMN_LINEAGE]
        self.assertEqual(sorted(documented), sorted(self.row.keys()))
        self.assertEqual(len(documented), len(set(documented)))

    def test_no_direct_identifier_is_carried_raw(self) -> None:
        for column in COLUMN_LINEAGE:
            if column["kind"] != "carried":
                continue
            with self.subTest(column=column["column"]):
                for identifier in DIRECT_IDENTIFIERS:
                    self.assertNotIn(identifier, column["sources"])

    def test_both_direct_identifiers_are_tokenized_somewhere(self) -> None:
        tokenized_sources = {
            source
            for column in COLUMN_LINEAGE
            if column["kind"] == "tokenized"
            for source in column["sources"]
        }
        for identifier in DIRECT_IDENTIFIERS:
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, tokenized_sources)

    def test_every_column_states_a_rule(self) -> None:
        for column in COLUMN_LINEAGE:
            with self.subTest(column=column["column"]):
                self.assertTrue(column["rule"].strip())

    def test_summary_counts_match_the_table(self) -> None:
        summary = lineage_summary()
        self.assertEqual(summary["columns"], len(COLUMN_LINEAGE))
        self.assertEqual(
            summary["tokenized"], sum(1 for c in COLUMN_LINEAGE if c["kind"] == "tokenized")
        )
        self.assertEqual(summary["direct_identifiers_in_source"], len(DIRECT_IDENTIFIERS))


if __name__ == "__main__":
    unittest.main()
