"""Column-level lineage for the curated login fact.

The mapping is declared here next to the transform it describes, so lineage is reviewed in the
same diff as the code that produces it. Every entry names the source fields it derives from and
how, which is what makes the privacy claim auditable: a curated column either carries no direct
identifier, or it is a keyed token of one.
"""

from typing import Any

# kind: "carried" (copied as-is), "derived" (computed), "tokenized" (irreversible without the
# secret), "generated" (produced by the load, not present in the source).
COLUMN_LINEAGE: list[dict[str, Any]] = [
    {
        "column": "event_id",
        "kind": "tokenized",
        "sources": ["<entire source payload>"],
        "rule": "HMAC-SHA256 over the canonical source hash, keyed by HASH_SECRET",
        "carries_identifier": False,
        "note": "Deterministic, so a redelivered message collides and is ignored on insert.",
    },
    {
        "column": "batch_id",
        "kind": "generated",
        "sources": [],
        "rule": "Assigned per ingestion run, joins the row to its audit record",
        "carries_identifier": False,
        "note": "Every curated row is traceable to one entry in ingestion_audit.",
    },
    {
        "column": "user_id",
        "kind": "carried",
        "sources": ["user_id"],
        "rule": "Copied unchanged",
        "carries_identifier": True,
        "note": "Pseudonymous in the source. Kept joinable on purpose; it is the analytic grain.",
    },
    {
        "column": "device_type",
        "kind": "derived",
        "sources": ["device_type"],
        "rule": "Lowercased, rejected unless ios, android, or web",
        "carries_identifier": False,
        "note": "Closed domain, so downstream dimensions cannot drift.",
    },
    {
        "column": "masked_ip",
        "kind": "tokenized",
        "sources": ["ip"],
        "rule": "HMAC-SHA256 keyed by HASH_SECRET",
        "carries_identifier": False,
        "note": "Plain hashing is insufficient here: IPv4 is a 32-bit space and falls to a sweep.",
    },
    {
        "column": "masked_device_id",
        "kind": "tokenized",
        "sources": ["device_id"],
        "rule": "HMAC-SHA256 keyed by HASH_SECRET",
        "carries_identifier": False,
        "note": "Stable per device, so repeat visits still join without storing the identifier.",
    },
    {
        "column": "locale",
        "kind": "carried",
        "sources": ["locale"],
        "rule": "Copied unchanged",
        "carries_identifier": False,
        "note": "",
    },
    {
        "column": "event_time_utc",
        "kind": "carried",
        "sources": ["event_time_utc"],
        "rule": "Copied, falling back to ingestion time when the producer omits it",
        "carries_identifier": False,
        "note": "Event time and load time are kept separate columns, never conflated.",
    },
    {
        "column": "auth_result",
        "kind": "derived",
        "sources": ["auth_result"],
        "rule": "Lowercased, rejected unless success or failure, defaults to success",
        "carries_identifier": False,
        "note": "",
    },
    {
        "column": "risk_band",
        "kind": "derived",
        "sources": ["risk_band"],
        "rule": "Lowercased, rejected unless low, medium, or high, defaults to low",
        "carries_identifier": False,
        "note": "",
    },
    {
        "column": "app_version",
        "kind": "derived",
        "sources": ["app_version"],
        "rule": "Major component parsed to an integer, rejected if unparseable",
        "carries_identifier": False,
        "note": "Analysable as a number while the original string is kept beside it.",
    },
    {
        "column": "app_version_raw",
        "kind": "carried",
        "sources": ["app_version"],
        "rule": "Copied unchanged",
        "carries_identifier": False,
        "note": "Keeps the parse reversible for investigation.",
    },
    {
        "column": "source_event_hash",
        "kind": "derived",
        "sources": ["<entire source payload>"],
        "rule": "SHA-256 over the key-sorted canonical JSON",
        "carries_identifier": False,
        "note": "Lets a quarantined payload be matched to a curated row without storing either.",
    },
    {
        "column": "pii_strategy",
        "kind": "generated",
        "sources": [],
        "rule": "Constant: hmac_sha256_secret_salted",
        "carries_identifier": False,
        "note": "Stamped on every row so a future strategy change stays distinguishable.",
    },
    {
        "column": "create_date",
        "kind": "derived",
        "sources": [],
        "rule": "Date part of the ingestion timestamp",
        "carries_identifier": False,
        "note": "Partition key candidate.",
    },
    {
        "column": "ingested_at_utc",
        "kind": "generated",
        "sources": [],
        "rule": "Load timestamp",
        "carries_identifier": False,
        "note": "",
    },
]

# Source fields that must never appear in the curated model in raw form.
DIRECT_IDENTIFIERS = ("ip", "device_id")


def lineage_summary() -> dict[str, Any]:
    """Counts the page states, computed rather than asserted."""
    tokenized = [c for c in COLUMN_LINEAGE if c["kind"] == "tokenized"]
    return {
        "columns": len(COLUMN_LINEAGE),
        "tokenized": len(tokenized),
        "direct_identifiers_in_source": len(DIRECT_IDENTIFIERS),
        "direct_identifiers_in_curated_model": sum(
            1 for c in COLUMN_LINEAGE if c["carries_identifier"] and c["kind"] == "carried"
        ),
        "columns_carrying_an_identifier": [
            c["column"] for c in COLUMN_LINEAGE if c["carries_identifier"]
        ],
    }
