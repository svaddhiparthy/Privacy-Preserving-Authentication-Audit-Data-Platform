import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pramanaledger import (
    REQUIRED_FIELDS,
    canonical_event_hash,
    hash_value,
    hmac_value,
    parse_major_version,
    transform_event,
    validate_event,
)
from pramanaledger.config import Settings
from pramanaledger.postgres import (
    ensure_table_exists,
    get_db_connection,
    insert_audit,
    insert_events,
    insert_quarantine,
)
from pramanaledger.runner import run
from pramanaledger.sqs import (
    build_sqs_client,
    delete_processed_messages,
    fetch_messages,
    parse_messages,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)

__all__ = [
    "REQUIRED_FIELDS",
    "Settings",
    "build_sqs_client",
    "canonical_event_hash",
    "delete_processed_messages",
    "ensure_table_exists",
    "fetch_messages",
    "get_db_connection",
    "hash_value",
    "hmac_value",
    "insert_audit",
    "insert_events",
    "insert_quarantine",
    "parse_major_version",
    "parse_messages",
    "run",
    "transform_event",
    "validate_event",
]


if __name__ == "__main__":
    raise SystemExit(run())
