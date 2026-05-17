from datetime import datetime, timezone
import unittest

from code_fetch_vaddhiparthy import hash_value, hmac_value, parse_major_version, transform_event


class TransformEventTests(unittest.TestCase):
    def test_hash_value_is_stable(self) -> None:
        self.assertEqual(hash_value("abc"), hash_value("abc"))

    def test_parse_major_version_returns_integer(self) -> None:
        self.assertEqual(parse_major_version("5.2.3"), 5)

    def test_transform_event_masks_sensitive_fields(self) -> None:
        event = {
            "user_id": "user_123",
            "device_type": "android",
            "device_id": "A1B2C3D4",
            "ip": "192.168.1.10",
            "locale": "en_US",
            "app_version": "5.2.3",
        }
        result = transform_event(event, ingested_at=datetime(2026, 4, 23, tzinfo=timezone.utc))

        self.assertEqual(result["user_id"], "user_123")
        self.assertEqual(result["masked_device_id"], hmac_value("A1B2C3D4", "local-demo-secret"))
        self.assertEqual(result["masked_ip"], hmac_value("192.168.1.10", "local-demo-secret"))
        self.assertEqual(result["app_version"], 5)
        self.assertEqual(result["auth_result"], "success")
        self.assertEqual(result["risk_band"], "low")
        self.assertEqual(result["create_date"].isoformat(), "2026-04-23")
        self.assertEqual(result["pii_strategy"], "hmac_sha256_secret_salted")

    def test_transform_event_requires_expected_fields(self) -> None:
        with self.assertRaises(ValueError):
            transform_event({"user_id": "user_123"})


if __name__ == "__main__":
    unittest.main()
