import json
import logging
import os
from datetime import datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

kinesis = boto3.client("kinesis")
STREAM_NAME = os.environ["KINESIS_STREAM_NAME"]


def handler(event, context):
    """Normalize incoming security events and forward them to Kinesis."""
    logger.info("Received event: %s", json.dumps(event))

    try:
        source = event.get("source", "unknown")
        detail = event.get("detail", {})

        normalized_event = {
            "event_id": event.get("id", f"event-{datetime.utcnow().timestamp():.0f}"),
            "timestamp": event.get("time", datetime.utcnow().isoformat()),
            "source": source,
            "account_id": event.get("account", "unknown"),
            "region": event.get("region", "unknown"),
            "event_type": event.get("detail-type", "unknown"),
            "severity": extract_severity(detail, source),
            "raw_event": detail,
        }

        logger.info("Normalized event: %s", json.dumps(normalized_event))

        response = kinesis.put_record(
            StreamName=STREAM_NAME,
            Data=json.dumps(normalized_event),
            PartitionKey=normalized_event["event_id"],
        )

        logger.info("Event sent to Kinesis sequence=%s", response["SequenceNumber"])

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Event processed successfully",
                    "sequence_number": response["SequenceNumber"],
                }
            ),
        }

    except Exception as exc:  # pragma: no cover - surfaced via CloudWatch logs
        logger.error("Error processing event: %s", exc, exc_info=True)
        raise


def extract_severity(detail, source):
    """Derive a severity label from the incoming event detail."""
    try:
        if source == "aws.guardduty":
            severity_score = detail.get("severity", 0)
            return severity_from_score(severity_score, [7, 4, 1])

        if source == "aws.securityhub":
            normalized = detail.get("Severity", {}).get("Normalized", 0)
            return severity_from_score(normalized, [70, 40, 1])

        return "MEDIUM"

    except Exception as exc:  # pragma: no cover - defensive logging only
        logger.warning("Failed to extract severity: %s", exc)
        return "MEDIUM"


def severity_from_score(score, thresholds):
    """Map a numeric score to LOW/MEDIUM/HIGH/CRITICAL buckets."""
    critical, high, medium = thresholds
    if score >= critical:
        return "CRITICAL"
    if score >= high:
        return "HIGH"
    if score >= medium:
        return "MEDIUM"
    return "LOW"
