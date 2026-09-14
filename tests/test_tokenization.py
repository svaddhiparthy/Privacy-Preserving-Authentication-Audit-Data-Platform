"""Hashing and secret-keyed tokenization primitives."""

import hashlib
import hmac
import unittest

from authaudit.tokenization import hash_value, hmac_value


class HashValueTests(unittest.TestCase):
    def test_is_sha256_hex(self) -> None:
        self.assertEqual(hash_value("abc"), hashlib.sha256(b"abc").hexdigest())
        self.assertEqual(len(hash_value("abc")), 64)

    def test_is_deterministic(self) -> None:
        self.assertEqual(hash_value("abc"), hash_value("abc"))

    def test_differs_for_different_input(self) -> None:
        self.assertNotEqual(hash_value("abc"), hash_value("abd"))

    def test_handles_unicode(self) -> None:
        self.assertEqual(len(hash_value("Trøndelag")), 64)


class HmacValueTests(unittest.TestCase):
    def test_matches_stdlib_hmac_sha256(self) -> None:
        expected = hmac.new(b"secret", b"10.0.0.1", hashlib.sha256).hexdigest()
        self.assertEqual(hmac_value("10.0.0.1", "secret"), expected)

    def test_is_deterministic_for_one_secret(self) -> None:
        self.assertEqual(hmac_value("10.0.0.1", "s"), hmac_value("10.0.0.1", "s"))

    def test_changes_with_the_secret(self) -> None:
        self.assertNotEqual(hmac_value("10.0.0.1", "s1"), hmac_value("10.0.0.1", "s2"))

    def test_is_not_a_plain_hash_of_the_value(self) -> None:
        """The point of keying: an unsalted rainbow table must not resolve the token."""
        self.assertNotEqual(hmac_value("10.0.0.1", "secret"), hash_value("10.0.0.1"))

    def test_small_input_space_is_not_reversible_without_the_secret(self) -> None:
        """A /24 sweep with the wrong secret must not recover the token."""
        token = hmac_value("192.168.1.10", "the-real-secret")
        guesses = {hmac_value(f"192.168.1.{n}", "a-guessed-secret") for n in range(256)}
        self.assertNotIn(token, guesses)


if __name__ == "__main__":
    unittest.main()
