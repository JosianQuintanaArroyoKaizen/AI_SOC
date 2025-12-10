"""
LLM-based Severity Scoring Lambda
Uses Claude Sonnet to intelligently score CloudTrail events on a 0-10 scale
and assign appropriate severity levels.
"""

import json
import logging
import os
from datetime import datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def handler(event, context):
    """Score event severity using Claude Sonnet."""
    logger.info("Scoring severity for event")
    
    try:
        raw_event = event.get("raw_event", {})
        event_type = event.get("event_type", "unknown")
        source = event.get("source", "unknown")
        
        # Skip if already has a good severity from GuardDuty/SecurityHub
        if source in ["aws.guardduty", "aws.securityhub"]:
            logger.info("Event from %s already has severity, skipping LLM scoring", source)
            return event
        
        # Get LLM-based severity score
        severity_analysis = score_with_llm(raw_event, event_type, source)
        
        # Update event with LLM severity
        event["severity"] = severity_analysis["severity"]
        event["severity_score"] = severity_analysis["score"]
        event["severity_reasoning"] = severity_analysis["reasoning"]
        event["scored_at"] = datetime.utcnow().isoformat()
        
        logger.info(
            "Severity scored: %s (score: %s/10)",
            severity_analysis["severity"],
            severity_analysis["score"]
        )
        
        return event
        
    except Exception as exc:
        logger.error("Error scoring severity: %s", exc, exc_info=True)
        # Fallback to MEDIUM on error
        event["severity"] = event.get("severity", "MEDIUM")
        event["severity_error"] = str(exc)
        return event


def score_with_llm(raw_event, event_type, source):
    """Use Claude to score event severity on 0-10 scale."""
    
    prompt = f"""You are a cybersecurity analyst evaluating AWS CloudTrail events for threat severity.

Analyze this CloudTrail event and assign a severity score from 0-10:

**Event Type:** {event_type}
**Event Source:** {source}

**Event Details:**
{json.dumps(raw_event, indent=2)[:3000]}

Scoring Guidelines:
- 0-2: LOW - Normal administrative actions, read-only operations, expected behavior
- 3-4: LOW-MEDIUM - Routine changes, standard operations with low risk
- 5-6: MEDIUM - Configuration changes, potential misconfigurations, requires monitoring
- 7-8: HIGH - Suspicious patterns, privilege escalations, security-relevant changes
- 9-10: CRITICAL - Known attack patterns, credential exposure, unauthorized access, data exfiltration

Consider:
1. **Action Impact**: What resources are affected? Can this cause damage?
2. **Access Patterns**: Is this unusual access or timing?
3. **User Identity**: Is this a service role, human user, or root account?
4. **Error Codes**: Failed access attempts may indicate reconnaissance
5. **Known Attack Vectors**: Does this match known attack techniques (MITRE ATT&CK)?

Respond ONLY with valid JSON in this exact format:
{{
  "score": <number 0-10>,
  "severity": "<CRITICAL|HIGH|MEDIUM|LOW>",
  "reasoning": "<brief 1-2 sentence explanation>",
  "risk_factors": ["<factor1>", "<factor2>"],
  "mitre_techniques": ["<technique_id if applicable>"]
}}"""

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "temperature": 0.1,  # Low temperature for consistent scoring
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
        )
        
        response_body = json.loads(response["body"].read())
        content = response_body["content"][0]["text"]
        
        # Parse JSON response
        # Try to extract JSON if wrapped in markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        analysis = json.loads(content)
        
        # Validate and normalize
        score = float(analysis.get("score", 5))
        score = max(0, min(10, score))  # Clamp to 0-10
        
        severity = analysis.get("severity", score_to_severity(score))
        
        return {
            "score": score,
            "severity": severity,
            "reasoning": analysis.get("reasoning", "LLM analysis completed"),
            "risk_factors": analysis.get("risk_factors", []),
            "mitre_techniques": analysis.get("mitre_techniques", [])
        }
        
    except Exception as exc:
        logger.error("LLM scoring failed: %s", exc, exc_info=True)
        # Fallback to heuristic scoring
        return fallback_scoring(raw_event, event_type)


def score_to_severity(score):
    """Convert 0-10 score to severity label."""
    if score >= 9:
        return "CRITICAL"
    elif score >= 7:
        return "HIGH"
    elif score >= 5:
        return "MEDIUM"
    else:
        return "LOW"


def fallback_scoring(raw_event, event_type):
    """Simple heuristic-based scoring if LLM fails."""
    score = 5  # Default MEDIUM
    
    # Check for suspicious patterns
    error_code = raw_event.get("errorCode")
    event_name = raw_event.get("eventName", "")
    user_identity = raw_event.get("userIdentity", {})
    
    # Higher risk indicators
    high_risk_actions = [
        "DeleteBucket", "DeleteUser", "DeleteRole", "PutBucketPolicy",
        "CreateAccessKey", "UpdateAccessKey", "AttachUserPolicy",
        "PutUserPolicy", "AssumeRole", "GetSecretValue"
    ]
    
    critical_actions = [
        "DeleteTrail", "StopLogging", "DeleteFlowLogs",
        "DisableSecurityHub", "DeleteDetector"
    ]
    
    # Root account usage is higher risk
    if user_identity.get("type") == "Root":
        score += 2
    
    # Failed access attempts
    if error_code in ["AccessDenied", "UnauthorizedOperation"]:
        score += 1
    
    # High-risk actions
    if any(action in event_name for action in high_risk_actions):
        score += 2
    
    # Critical actions
    if any(action in event_name for action in critical_actions):
        score += 4
    
    score = max(0, min(10, score))
    
    return {
        "score": score,
        "severity": score_to_severity(score),
        "reasoning": "Heuristic-based scoring (LLM unavailable)",
        "risk_factors": [],
        "mitre_techniques": []
    }
