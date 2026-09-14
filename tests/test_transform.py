"""Validation, version parsing, canonical hashing, and the curated transform."""

import os
import unittest
from datetime import UTC, datetime

from authaudit.config import DEMO_HASH_SECRET, hash_secret_is_demo
from authaudit.transform import (
    REQUIRED_FIELDS,
    canonical_event_hash,
    parse_major_version,
    transform_event,
    validate_event,
)

VALID_EVENT = {
    "user_id": "user_123",
    "device_type": "android",
    "device_id": "A1B2C3D4",
    "ip": "192.168.1.10",
    "locale": "en_US",
    "app_version": "5.2.3",
}


class ValidateEventTests(unittest.TestCase):
    def test_accepts_a_complete_event(self) -> None:
        validate_event(dict(VALID_EVENT))

    def test_rejects_each_missing_required_field(self) -> None:
        for field in sorted(REQUIRED_FIELDS):
            event = dict(VALID_EVENT)
            del event[field]
            with self.subTest(field=field), self.assertRaises(ValueError) as caught:
                validate_event(event)
            self.assertIn(field, str(caught.exception))

    def test_rejects_blank_user_id(self) -> None:
        with self.assertRaises(ValueError):
            validate_event(dict(VALID_EVENT, user_id="   "))

    def test_rejects_device_type_outside_the_domain(self) -> None:
        with self.assertRaises(ValueError):
            validate_event(dict(VALID_EVENT, device_type="smart-fridge"))

    def test_accepts_every_allowed_device_type(self) -> None:
        for device_type in ("ios", "android", "web", "iOS", "WEB"):
            with self.subTest(device_type=device_type):
                validate_event(dict(VALID_EVENT, device_type=device_type))

    def test_rejects_unknown_auth_result(self) -> None:
        with self.assertRaises(ValueError):
            validate_event(dict(VALID_EVENT, auth_result="maybe"))

    def test_rejects_unknown_risk_band(self) -> None:
        with self.assertRaises(ValueError):
            validate_event(dict(VALID_EVENT, risk_band="critical"))

    def test_rejects_malformed_app_version(self) -> None:
        with self.assertRaises(ValueError):
            validate_event(dict(VALID_EVENT, app_version="five.two"))


class ParseMajorVersionTests(unittest.TestCase):
    def test_returns_the_major_component(self) -> None:
        self.assertEqual(parse_major_version("5.2.3"), 5)
        self.assertEqual(parse_major_version("12"), 12)
        self.assertEqual(parse_major_version("0.9"), 0)

    def test_raises_on_non_numeric_major(self) -> None:
        with self.assertRaises(ValueError):
            parse_major_version("v5.2")


class CanonicalEventHashTests(unittest.TestCase):
    def test_is_stable_for_the_same_event(self) -> None:
        self.assertEqual(
            canonical_event_hash(dict(VALID_EVENT)), canonical_event_hash(dict(VALID_EVENT))
        )

    def test_ignores_key_order(self) -> None:
        reordered = dict(reversed(list(VALID_EVENT.items())))
        self.assertEqual(canonical_event_hash(dict(VALID_EVENT)), canonical_event_hash(reordered))

    def test_changes_when_a_value_changes(self) -> None:
        self.assertNotEqual(
            canonical_event_hash(dict(VALID_EVENT)),
            canonical_event_hash(dict(VALID_EVENT, ip="10.0.0.1")),
        )


class TransformEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ingested_at = datetime(2026, 4, 23, tzinfo=UTC)
        self.row = transform_event(
            dict(VALID_EVENT), self.ingested_at, hash_secret="unit-test-secret"
        )

    def test_curated_row_carries_no_raw_identifiers(self) -> None:
        serialized = repr(self.row)
        self.assertNotIn(VALID_EVENT["ip"], serialized)
        self.assertNotIn(VALID_EVENT["device_id"], serialized)

    def test_masks_ip_and_device_id(self) -> None:
        self.assertNotEqual(self.row["masked_ip"], VALID_EVENT["ip"])
        self.assertNotEqual(self.row["masked_device_id"], VALID_EVENT["device_id"])
        self.assertEqual(len(self.row["masked_ip"]), 64)
        self.assertEqual(len(self.row["masked_device_id"]), 64)

    def test_keeps_user_id_joinable(self) -> None:
        self.assertEqual(self.row["user_id"], VALID_EVENT["user_id"])

    def test_normalizes_version_and_defaults(self) -> None:
        self.assertEqual(self.row["app_version"], 5)
        self.assertEqual(self.row["app_version_raw"], "5.2.3")
        self.assertEqual(self.row["auth_result"], "success")
        self.assertEqual(self.row["risk_band"], "low")
        self.assertEqual(self.row["pii_strategy"], "hmac_sha256_secret_salted")
        self.assertEqual(self.row["create_date"].isoformat(), "2026-04-23")

    def test_event_id_is_deterministic_for_replay(self) -> None:
        again = transform_event(dict(VALID_EVENT), self.ingested_at, hash_secret="unit-test-secret")
        self.assertEqual(self.row["event_id"], again["event_id"])

    def test_event_id_changes_with_the_secret(self) -> None:
        other = transform_event(dict(VALID_EVENT), self.ingested_at, hash_secret="another-secret")
        self.assertNotEqual(self.row["event_id"], other["event_id"])

    def test_tokens_differ_across_secrets(self) -> None:
        other = transform_event(dict(VALID_EVENT), self.ingested_at, hash_secret="another-secret")
        self.assertNotEqual(self.row["masked_ip"], other["masked_ip"])

    def test_invalid_event_is_rejected_not_coerced(self) -> None:
        with self.assertRaises(ValueError):
            transform_event({"user_id": "user_123"})

    def test_secret_comes_from_the_environment_when_not_passed(self) -> None:
        previous = os.environ.get("HASH_SECRET")
        try:
            os.environ["HASH_SECRET"] = "env-provided-secret"
            from_env = transform_event(dict(VALID_EVENT), self.ingested_at)
            expected = transform_event(
                dict(VALID_EVENT), self.ingested_at, hash_secret="env-provided-secret"
            )
            self.assertEqual(from_env["masked_ip"], expected["masked_ip"])
            self.assertNotEqual(from_env["masked_ip"], self.row["masked_ip"])
        finally:
            if previous is None:
                os.environ.pop("HASH_SECRET", None)
            else:
                os.environ["HASH_SECRET"] = previous


class HashSecretPolicyTests(unittest.TestCase):
    def test_demo_secret_is_detectable(self) -> None:
        self.assertTrue(hash_secret_is_demo(DEMO_HASH_SECRET))
        self.assertFalse(hash_secret_is_demo("a-real-secret"))


if __name__ == "__main__":
    unittest.main()
