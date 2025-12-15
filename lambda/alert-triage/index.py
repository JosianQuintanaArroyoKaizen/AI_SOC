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
        source = event.get("source", "unknown")
        event_type = event.get("event_type", "unknown")

        priority_score = calculate_priority(threat_score, source, event_type)
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


def calculate_priority(threat_score, source, event_type):
    """
    Calculate priority score based on ML threat score, source trust, and event criticality.
    
    Args:
        threat_score: ML model confidence score (0-1 range, typically)
        source: Event source (e.g., 'aws.guardduty', 'aws.securityhub')
        event_type: Type of security event
    
    Returns:
        Priority score (0-100)
    """
    # Convert threat_score to 0-100 range if it's in decimal format (0-1)
    if threat_score <= 1.0:
        base_score = threat_score * 100
    else:
        base_score = threat_score
    
    # Source trust multipliers - more reliable sources get higher weight
    source_weights = {
        "aws.guardduty": 1.2,      # GuardDuty is purpose-built for threat detection
        "aws.securityhub": 1.15,   # SecurityHub aggregates findings
        "aws.cloudtrail": 1.0,     # CloudTrail is raw audit logs
        "aws.config": 1.05,        # Config for compliance issues
    }
    
    # Critical event types that warrant immediate attention
    critical_events = [
        "GuardDuty Finding",
        "UnauthorizedAccess",
        "Recon",
        "Trojan",
        "Backdoor",
        "Cryptomining",
        "RootCredentials",
        "IAMUser/AnomalousBehavior"
    ]
    
    # Apply source weight
    adjusted_score = base_score * source_weights.get(source, 1.0)
    
    # Boost score for critical event types
    if any(keyword in event_type for keyword in critical_events):
        adjusted_score *= 1.25
    
    # Ensure score is within 0-100 range
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
