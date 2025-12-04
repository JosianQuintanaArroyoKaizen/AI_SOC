import json
import logging
import os
from datetime import datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

runtime = boto3.client("sagemaker-runtime")
ENDPOINT_NAME = os.environ["SAGEMAKER_ENDPOINT"]


def handler(event, context):
    """Call the SageMaker endpoint and attach prediction metadata."""
    try:
        features = extract_features(event)
        logger.debug("Features prepared: %s", features)

        response = runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType="application/json",
            Body=json.dumps(features),
        )

        result = json.loads(response["Body"].read().decode())
        threat_score = float(result["predictions"][0])

        event["ml_prediction"] = {
            "threat_score": threat_score,
            "model_version": result.get("model_version", "1.0"),
            "evaluated_at": datetime.utcnow().isoformat(),
        }
        return event

    except Exception as exc:  # pragma: no cover - surfaced via CloudWatch logs
        logger.error("Error invoking SageMaker endpoint: %s", exc, exc_info=True)
        event["ml_prediction"] = {"threat_score": 0.0, "error": str(exc)}
        return event


def extract_features(event):
    """Map raw event payload into the feature vector expected by the model."""
    raw_event = event.get("raw_event", {})

    features = {
        "api_call_count": raw_event.get("apiCallCount", 1),
        "error_rate": 0 if raw_event.get("errorCode") is None else 1,
        "source_ip_reputation": raw_event.get("ipReputation", 0.5),
        "time_of_day": get_hour_of_day(event.get("timestamp", datetime.utcnow().isoformat())),
        "user_history_score": raw_event.get("userHistoryScore", 0.7),
    }
    return features


def get_hour_of_day(timestamp):
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return dt.hour
