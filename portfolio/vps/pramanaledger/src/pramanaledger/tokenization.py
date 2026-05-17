import hashlib
import hmac


def hash_value(raw_value: str) -> str:
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def hmac_value(raw_value: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        raw_value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
