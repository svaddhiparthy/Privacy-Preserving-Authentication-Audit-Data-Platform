"""Queue intake parsing: what survives a malformed or incomplete message."""

import json
import unittest

from authaudit.sqs import parse_messages


def message(body: dict, receipt: str = "rh-1") -> dict:
    return {"Body": json.dumps(body), "ReceiptHandle": receipt}


class ParseMessagesTests(unittest.TestCase):
    def test_returns_payload_and_receipt_pairs(self) -> None:
        parsed = parse_messages([message({"user_id": "u1"}, "rh-1")])
        self.assertEqual(parsed, [({"user_id": "u1"}, "rh-1")])

    def test_preserves_order(self) -> None:
        parsed = parse_messages(
            [
                message({"user_id": "u1"}, "rh-1"),
                message({"user_id": "u2"}, "rh-2"),
            ]
        )
        self.assertEqual([handle for _, handle in parsed], ["rh-1", "rh-2"])

    def test_skips_messages_without_a_receipt_handle(self) -> None:
        """Without a handle the message cannot be deleted, so processing it would loop."""
        parsed = parse_messages(
            [
                {"Body": json.dumps({"user_id": "u1"})},
                message({"user_id": "u2"}, "rh-2"),
            ]
        )
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0][1], "rh-2")

    def test_empty_batch_returns_empty(self) -> None:
        self.assertEqual(parse_messages([]), [])

    def test_malformed_json_body_raises(self) -> None:
        """Surfacing the error is correct: a broken body must not be silently dropped."""
        with self.assertRaises(json.JSONDecodeError):
            parse_messages([{"Body": "{not json", "ReceiptHandle": "rh-1"}])


if __name__ == "__main__":
    unittest.main()
