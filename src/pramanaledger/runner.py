import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from pramanaledger.config import Settings
from pramanaledger.postgres import (
    ensure_table_exists,
    get_db_connection,
    insert_audit,
    insert_events,
    insert_quarantine,
)
from pramanaledger.sqs import delete_processed_messages, fetch_messages, parse_messages
from pramanaledger.transform import transform_event

LOGGER = logging.getLogger(__name__)


def run(settings: Settings | None = None) -> int:
    settings = settings or Settings()
    batch_id = uuid4().hex
    started_at = datetime.now(timezone.utc)
    messages = fetch_messages(settings)
    if not messages:
        LOGGER.info("No messages available in queue %s", settings.sqs_queue_url)
        return 0

    parsed_messages = parse_messages(messages)
    transformed_rows: list[dict] = []
    rejected_rows: list[dict] = []
    processed_receipts: list[str] = []

    for event, receipt_handle in parsed_messages:
        try:
            transformed_rows.append(
                transform_event(event, hash_secret=settings.hash_secret, batch_id=batch_id)
            )
            processed_receipts.append(receipt_handle)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            LOGGER.warning("Quarantining invalid event: %s", exc)
            rejected_rows.append(
                {
                    "batch_id": batch_id,
                    "rejected_at_utc": datetime.now(timezone.utc),
                    "error_message": str(exc),
                    "payload": json.dumps(event),
                }
            )
            if settings.quarantine_invalid_events:
                processed_receipts.append(receipt_handle)

    if not transformed_rows and not rejected_rows:
        LOGGER.warning("No parsable events were found in %s messages", len(messages))
        return 1

    with get_db_connection(settings) as connection:
        with connection.cursor() as cursor:
            ensure_table_exists(cursor, settings.db_schema)
            insert_events(cursor, transformed_rows, settings.db_schema)
            insert_quarantine(cursor, batch_id, rejected_rows, settings.db_schema)
            insert_audit(
                cursor,
                schema=settings.db_schema,
                batch_id=batch_id,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                messages_received=len(messages),
                records_loaded=len(transformed_rows),
                records_rejected=len(rejected_rows),
            )
        connection.commit()

    delete_processed_messages(settings, processed_receipts)
    LOGGER.info(
        "Batch %s loaded=%s rejected=%s received=%s",
        batch_id,
        len(transformed_rows),
        len(rejected_rows),
        len(messages),
    )
    return 0
