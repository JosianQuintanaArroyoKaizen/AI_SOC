#!/usr/bin/env python3
"""
Score CloudTrail Events with Claude Sonnet
Creates labeled training data with severity scores for better ML model training
"""

import json
import os
import time
from pathlib import Path

import boto3

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    def tqdm(iterable, **kwargs):
        """Fallback progress indicator if tqdm not available"""
        total = len(iterable) if hasattr(iterable, '__len__') else None
        desc = kwargs.get('desc', 'Processing')
        for i, item in enumerate(iterable):
            if total and (i % 10 == 0 or i == total - 1):
                print(f"\r{desc}: {i+1}/{total} ({((i+1)/total*100):.1f}%)", end='', flush=True)
            yield item
        if total:
            print()  # New line after completion

# Configuration
INPUT_FILE = "datasets/aws_samples/shared_services.json"
OUTPUT_FILE = "datasets/aws_samples/shared_services_labeled.json"
BATCH_SIZE = 10  # Process in batches to show progress
MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"  # Claude 3.5 Sonnet
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1  # seconds

bedrock = boto3.client("bedrock-runtime", region_name="eu-central-1")


def score_event_with_llm(event):
    """Score a single CloudTrail event using Claude."""
    
    event_name = event.get("eventName", "Unknown")
    event_source = event.get("eventSource", "unknown")
    user_identity = event.get("userIdentity", {})
    
    prompt = f"""You are a cybersecurity analyst evaluating AWS CloudTrail events for threat severity.

Analyze this CloudTrail event and assign a severity score from 0-10:

**Event Name:** {event_name}
**Event Source:** {event_source}
**User Type:** {user_identity.get('type', 'Unknown')}

**Full Event:**
{json.dumps(event, indent=2)[:2500]}

Scoring Guidelines:
- 0-2: LOW - Normal administrative actions, read-only operations, expected behavior
- 3-4: LOW-MEDIUM - Routine changes, standard operations with low risk  
- 5-6: MEDIUM - Configuration changes, potential misconfigurations, requires monitoring
- 7-8: HIGH - Suspicious patterns, privilege escalations, security-relevant changes
- 9-10: CRITICAL - Known attack patterns, credential exposure, unauthorized access

Consider:
1. Action Impact: Resource changes, permissions, data access
2. User Identity: Root account, IAM user, service role
3. Error Codes: Failed attempts may indicate reconnaissance
4. Known Attack Patterns: MITRE ATT&CK techniques

Respond ONLY with valid JSON:
{{
  "score": <number 0-10>,
  "severity": "<CRITICAL|HIGH|MEDIUM|LOW>",
  "reasoning": "<1-2 sentence explanation>",
  "risk_factors": ["<factor1>", "<factor2>"]
}}"""

    # Retry with exponential backoff for throttling
    for attempt in range(MAX_RETRIES):
        try:
            response = bedrock.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 400,
                    "temperature": 0.1,
                    "messages": [{"role": "user", "content": prompt}]
                })
            )
            
            response_body = json.loads(response["body"].read())
            content = response_body["content"][0]["text"]
            
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            
            # Validate
            score = float(analysis.get("score", 5))
            score = max(0, min(10, score))
            
            return {
                "score": score,
                "severity": analysis.get("severity", score_to_severity(score)),
                "reasoning": analysis.get("reasoning", ""),
                "risk_factors": analysis.get("risk_factors", [])
            }
            
        except Exception as e:
            error_str = str(e)
            # Check for throttling errors
            if "ThrottlingException" in error_str or "TooManyRequestsException" in error_str:
                if attempt < MAX_RETRIES - 1:
                    retry_delay = INITIAL_RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    print(f"  ⏳ Throttled, retrying in {retry_delay}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                    time.sleep(retry_delay)
                    continue
            
            # For other errors or final retry, fall back
            print(f"  ⚠️  Error scoring event {event_name}: {e}")
            return fallback_score(event)
    
    # If all retries exhausted
    print(f"  ⚠️  Max retries exceeded for event {event_name}")
    return fallback_score(event)


def score_to_severity(score):
    """Convert numeric score to severity label."""
    if score >= 9:
        return "CRITICAL"
    elif score >= 7:
        return "HIGH"
    elif score >= 5:
        return "MEDIUM"
    else:
        return "LOW"


def fallback_score(event):
    """Simple heuristic if LLM fails."""
    event_name = event.get("eventName", "")
    error_code = event.get("errorCode")
    user_type = event.get("userIdentity", {}).get("type", "")
    
    score = 3  # Default LOW-MEDIUM
    
    # Risk indicators
    if user_type == "Root":
        score += 3
    if error_code in ["AccessDenied", "UnauthorizedOperation"]:
        score += 2
    if any(word in event_name for word in ["Delete", "Put", "Update", "Create"]):
        score += 1
    
    score = min(10, score)
    
    return {
        "score": score,
        "severity": score_to_severity(score),
        "reasoning": "Heuristic scoring (LLM unavailable)",
        "risk_factors": []
    }


def main():
    print("🤖 CloudTrail Event Severity Scorer")
    print("=" * 60)
    
    # Load events
    print(f"\n📂 Loading events from: {INPUT_FILE}")
    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)
    
    # Handle both array format and CloudTrail Records format
    if isinstance(data, dict) and 'Records' in data:
        events = data['Records']
    elif isinstance(data, list):
        events = data
    else:
        raise ValueError("Unexpected JSON format - expected array or {'Records': [...]}")
    
    total_events = len(events)
    print(f"✅ Loaded {total_events:,} events")
    
    # Score events
    print(f"\n🔍 Scoring events with Claude Sonnet...")
    print(f"   Model: {MODEL_ID}")
    print(f"   Batch size: {BATCH_SIZE}")
    
    labeled_events = []
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    
    for i, event in enumerate(tqdm(events, desc="Scoring")):
        # Score with LLM
        severity_data = score_event_with_llm(event)
        
        # Normalize severity to standard categories
        severity = severity_data["severity"].upper()
        # Map any variations to standard categories
        if "LOW" in severity and "MEDIUM" in severity:
            severity = "MEDIUM"  # LOW-MEDIUM becomes MEDIUM
        elif severity not in severity_counts:
            severity = "MEDIUM"  # Default to MEDIUM for unknown
        
        # Add severity info to event
        event["llm_severity_score"] = severity_data["score"]
        event["llm_severity"] = severity
        event["llm_reasoning"] = severity_data["reasoning"]
        event["llm_risk_factors"] = severity_data["risk_factors"]
        
        labeled_events.append(event)
        severity_counts[severity] += 1
        
        # Rate limiting - Bedrock has limits
        if (i + 1) % BATCH_SIZE == 0:
            time.sleep(0.5)
    
    # Save labeled dataset
    print(f"\n💾 Saving labeled dataset to: {OUTPUT_FILE}")
    output_path = Path(OUTPUT_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(labeled_events, f, indent=2)
    
    # Statistics
    print("\n" + "=" * 60)
    print("📊 Severity Distribution:")
    print("=" * 60)
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = severity_counts[severity]
        percentage = (count / total_events) * 100
        bar = "█" * int(percentage / 2)
        print(f"{severity:10} {count:5} ({percentage:5.1f}%) {bar}")
    
    print(f"\n✅ Complete! Labeled dataset saved to: {OUTPUT_FILE}")
    print(f"📈 Use this labeled data to retrain your ML model with better severity classification")


if __name__ == "__main__":
    main()
