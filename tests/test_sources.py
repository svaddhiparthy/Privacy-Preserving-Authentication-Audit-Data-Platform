import csv
import json
import tempfile
import unittest
from pathlib import Path

from pramanaledger.sources import normalize_rba_row, write_normalized_sample


class RbaSourceTests(unittest.TestCase):
    def test_normalize_rba_row_maps_login_fields(self) -> None:
        row = {
            "IP Address": "203.0.113.10",
            "Country": "US",
            "Region": "NC",
            "City": "Charlotte",
            "ASN": "64512",
            "User Agent String": "Mozilla/5.0",
            "OS Name and Version": "Windows 11",
            "Browser Name and Version": "Chrome 120",
            "Device Type": "desktop",
            "User ID": "42",
            "Login Timestamp": "1640995200",
            "Round-Trip Time (RTT) [ms]": "31",
            "Login Successful": "False",
            "Is Attack IP": "True",
            "Is Account Takeover": "False",
        }
        normalized = normalize_rba_row(row)
        self.assertEqual(normalized["user_id"], "rba_user_42")
        self.assertEqual(normalized["device_type"], "web")
        self.assertEqual(normalized["auth_result"], "failure")
        self.assertEqual(normalized["risk_band"], "high")
        self.assertEqual(normalized["ip"], "203.0.113.10")

    def test_write_normalized_sample_from_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "rba.csv"
            output = Path(tmp) / "normalized.jsonl"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "IP Address",
                        "Country",
                        "Device Type",
                        "User ID",
                        "Login Timestamp",
                        "Login Successful",
                        "Is Attack IP",
                        "Is Account Takeover",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "IP Address": "198.51.100.7",
                        "Country": "US",
                        "Device Type": "mobile",
                        "User ID": "7",
                        "Login Timestamp": "1640995201",
                        "Login Successful": "True",
                        "Is Attack IP": "False",
                        "Is Account Takeover": "False",
                    }
            )
            self.assertEqual(write_normalized_sample(source, output, limit=10), 1)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["source_system"], "rba_dataset")


if __name__ == "__main__":
    unittest.main()
