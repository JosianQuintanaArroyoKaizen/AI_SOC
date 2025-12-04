import json
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Assign a priority score to an alert before orchestration."""
    logger.info("Received event for triage: %s", json.dumps(event))

    try:
        threat_score = event.get("ml_prediction", {}).get("threat_score", 0)
        severity = event.get("severity", "LOW")
        source = event.get("source", "unknown")
        event_type = event.get("event_type", "unknown")

        priority_score = calculate_priority(threat_score, severity, source, event_type)
        triage_info = {
            "priority_score": priority_score,
            "priority_level": get_priority_level(priority_score),
            "requires_human_review": priority_score > 80,
            "auto_remediate": priority_score > 90,
            "recommended_actions": get_recommended_actions(priority_score, event_type),
            "triage_timestamp": datetime.utcnow().isoformat(),
        }

        event["triage"] = triage_info
        logger.info(
            "Triage complete: priority=%s level=%s",
            priority_score,
            triage_info["priority_level"],
        )
        return event

    except Exception as exc:  # pragma: no cover - surfaced via CloudWatch logs
        logger.error("Error in triage: %s", exc, exc_info=True)
        event["triage"] = {"error": str(exc), "priority_score": 50, "priority_level": "MEDIUM"}
        return event


def calculate_priority(threat_score, severity, source, event_type):
    """Blend ML output, severity, and context into a 0-100 priority."""
    severity_weights = {"CRITICAL": 40, "HIGH": 30, "MEDIUM": 20, "LOW": 10}
    source_weights = {"aws.guardduty": 1.2, "aws.securityhub": 1.1, "aws.cloudtrail": 1.0}
    critical_events = ["GuardDuty Finding", "UnauthorizedAccess", "Recon", "Trojan"]

    base_score = (threat_score * 0.6) + severity_weights.get(severity, 10)
    adjusted_score = base_score * source_weights.get(source, 1.0)

    if any(keyword in event_type for keyword in critical_events):
        adjusted_score *= 1.3

    return min(100, max(0, adjusted_score))


def get_priority_level(score):
    if score >= 90:
        return "CRITICAL"
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def get_recommended_actions(priority_score, event_type):
    actions = []
    if priority_score >= 90:
        actions.extend(["IMMEDIATE_ISOLATION", "DISABLE_CREDENTIALS", "NOTIFY_SECURITY_TEAM"])
    elif priority_score >= 70:
        actions.extend(["INVESTIGATE", "MONITOR_CLOSELY", "NOTIFY_SECURITY_TEAM"])
    elif priority_score >= 40:
        actions.extend(["LOG_AND_MONITOR", "SCHEDULE_REVIEW"])
    else:
        actions.append("LOG_ONLY")
    return actions
