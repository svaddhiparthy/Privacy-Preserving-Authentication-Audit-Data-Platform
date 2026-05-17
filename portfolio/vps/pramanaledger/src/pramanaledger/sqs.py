import json
import logging
from typing import Any

from pramanaledger.config import Settings

LOGGER = logging.getLogger(__name__)


def build_sqs_client(settings: Settings):
    import boto3

    return boto3.client(
        "sqs",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.sqs_endpoint_url,
        region_name=settings.aws_region,
    )


def fetch_messages(settings: Settings) -> list[dict[str, Any]]:
    sqs = build_sqs_client(settings)
    response = sqs.receive_message(
        QueueUrl=settings.sqs_queue_url,
        MaxNumberOfMessages=settings.max_messages,
        WaitTimeSeconds=settings.wait_time_seconds,
        VisibilityTimeout=settings.visibility_timeout,
        MessageAttributeNames=["All"],
    )
    return response.get("Messages", [])


def parse_messages(messages: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str]]:
    parsed_messages: list[tuple[dict[str, Any], str]] = []
    for message in messages:
        receipt_handle = message.get("ReceiptHandle")
        body = message.get("Body", "")
        if not receipt_handle:
            LOGGER.warning("Skipping message without receipt handle: %s", message)
            continue
        parsed_messages.append((json.loads(body), receipt_handle))
    return parsed_messages


def delete_processed_messages(settings: Settings, receipt_handles: list[str]) -> None:
    if not receipt_handles:
        return

    sqs = build_sqs_client(settings)
    entries = [
        {"Id": str(index), "ReceiptHandle": receipt_handle}
        for index, receipt_handle in enumerate(receipt_handles)
    ]
    sqs.delete_message_batch(QueueUrl=settings.sqs_queue_url, Entries=entries)
