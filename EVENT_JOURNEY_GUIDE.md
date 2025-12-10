# Event Journey Through AI-SOC Pipeline - Production Flow

## Complete Production Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STAGE 1: EVENT DETECTION (AWS Services)                  │
│                                                                              │
│  GuardDuty detects:                    Security Hub aggregates:             │
│  • Malicious API calls                 • IAM policy violations              │
│  • Port scanning                       • S3 bucket misconfigurations        │
│  • Unauthorized access                 • Security group issues              │
│  • Trojan/malware activity             • Config compliance findings         │
│                                                                              │
│  CloudTrail logs:                                                           │
│  • All API calls in account                                                 │
│  • Resource changes                                                         │
│  • User activities                                                          │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   │ Emits event to EventBridge
                                   │ (Raw AWS service format)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STAGE 2: EVENT ROUTING (EventBridge)                     │
│                                                                              │
│   EventBridge Rules:                                                        │
│   • ai-soc-dev-guardduty-findings (source: aws.guardduty)                  │
│   • ai-soc-dev-securityhub-findings (source: aws.securityhub)              │
│                                                                              │
│   Matches event patterns and routes to Event Normalizer Lambda             │
│                                                                              │
│   Duration: ~50-100ms                                                       │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   │ Triggers Lambda with raw event
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                STAGE 3: EVENT NORMALIZATION (Lambda)                        │
│                     (ai-soc-dev-event-normalizer)                           │
│                                                                              │
│   • Receives raw AWS event (different formats per service)                 │
│   • Extracts common fields:                                                │
│     - event_id, timestamp, source, account_id, region                      │
│     - event_type, severity (mapped from service scores)                    │
│   • Preserves original event in raw_event field                            │
│   • Creates standardized schema for downstream processing                  │
│   • Publishes normalized event to Kinesis Stream                           │
│                                                                              │
│   Duration: ~200-500ms                                                      │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   │ Normalized event (no threat_score yet!)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                STAGE 4: EVENT BUFFERING (Kinesis Stream)                    │
│                     (ai-soc-dev-security-events)                            │
│                                                                              │
│   • High-throughput event buffer                                           │
│   • Allows multiple consumers                                              │
│   • 24-hour retention                                                       │
│   • Batches events for efficient processing                                │
│                                                                              │
│   Duration: ~100ms (buffering time)                                         │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   │ Batch of normalized events
                                   │ (triggers Lambda via Event Source Mapping)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                STAGE 5: ML THREAT SCORING (Lambda)                          │
│                     (ai-soc-dev-ml-inference)                               │
│                                                                              │
│   • Reads batch of events from Kinesis (up to 10 events)                  │
│   • Extracts features from each event:                                     │
│     - API call patterns, error rates, IP reputation                        │
│     - Time of day, user history, resource context                          │
│   • Calculates ML threat_score (0-100) using trained model                │
│   • Adds ml_prediction object to each event                                │
│   • Triggers Step Functions workflow for each scored event                 │
│                                                                              │
│   Duration: ~500ms - 1s per batch                                           │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   │ Event now has ml_prediction.threat_score
                                   │ Starts Step Functions execution
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STEP FUNCTIONS WORKFLOW                                │
│                     (ai-soc-dev-soc-workflow)                                │
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │  STATE 1: AlertTriage Lambda                                   │       │
│   │  ────────────────────────────                                  │       │
│   │  • Receives event WITH ML threat score                         │       │
│   │  • Calculates priority score using formula:                    │       │
│   │    base = (threat_score * 0.6) + severity_weight              │       │
│   │    priority = base * source_multiplier * event_type_boost     │       │
│   │  • Result: ~75-85 priority score                               │       │
│   │  • Assigns priority level: HIGH                                │       │
│   │  • Determines if auto-remediation needed (>90)                 │       │
│   │  • Adds triage metadata to event                               │       │
│   │                                                                 │       │
│   │  Duration: ~500ms                                              │       │
│   └───────────────────────────┬────────────────────────────────────┘       │
│                               │                                             │
│                               │ Event + triage data                         │
│                               ▼                                             │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │  STATE 2: CheckPriority (Choice State)                         │       │
│   │  ──────────────────────────────────                            │       │
│   │  IF priority_score > 70:                                       │       │
│   │     ├─→ Go to Bedrock Analysis (HIGH severity)                 │       │
│   │  ELSE:                                                          │       │
│   │     └─→ Go to LogLowPriority                                   │       │
│   │                                                                 │       │
│   │  Duration: ~50ms (just a conditional check)                    │       │
│   └───────────────────────────┬────────────────────────────────────┘       │
│                               │                                             │
│                               │ Priority = 75-85 (HIGH)                     │
│                               ▼                                             │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │  STATE 3: BedrockAnalysis Lambda                               │       │
│   │  ────────────────────────────────                              │       │
│   │  • Prepares context from event data                            │       │
│   │  • Constructs prompt for Claude AI                             │       │
│   │  • Calls Amazon Bedrock API                                    │       │
│   │    Model: Claude 3.7 Sonnet                                    │       │
│   │  • AI analyzes:                                                │       │
│   │    - Risk assessment (1-10 scale)                              │       │
│   │    - Attack vector identification                              │       │
│   │    - Recommended response actions                              │       │
│   │    - Business impact estimation                                │       │
│   │  • Parses AI response (JSON)                                   │       │
│   │  • Adds bedrock_analysis to event                              │       │
│   │                                                                 │       │
│   │  Duration: ~5-10 seconds (AI processing)                       │       │
│   └───────────────────────────┬────────────────────────────────────┘       │
│                               │                                             │
│                               │ Event + triage + AI analysis                │
│                               ▼                                             │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │  STATE 4: CheckAutoRemediate (Choice State)                    │       │
│   │  ────────────────────────────────────────                      │       │
│   │  IF priority_score > 90:                                       │       │
│   │     ├─→ Go to Remediation Lambda                               │       │
│   │  ELSE:                                                          │       │
│   │     └─→ Go to NotifySecurityTeam                               │       │
│   │                                                                 │       │
│   │  Duration: ~50ms                                               │       │
│   └───────────────────────────┬────────────────────────────────────┘       │
│                               │                                             │
│                               │ Priority = 75-85 (no auto-remediation)      │
│                               ▼                                             │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │  STATE 5: NotifySecurityTeam (SNS Task)                        │       │
│   │  ───────────────────────────────────                           │       │
│   │  • Publishes to SNS topic                                      │       │
│   │  • Includes:                                                   │       │
│   │    - Event ID                                                  │       │
│   │    - Priority level                                            │       │
│   │    - Threat score                                              │       │
│   │    - Bedrock risk score                                        │       │
│   │    - Message for human review                                  │       │
│   │  • SNS routes to:                                              │       │
│   │    - Email                                                     │       │
│   │    - Slack/PagerDuty (if configured)                           │       │
│   │                                                                 │       │
│   │  Duration: ~200ms                                              │       │
│   └───────────────────────────┬────────────────────────────────────┘       │
│                               │                                             │
│                               │ Notification sent                           │
│                               ▼                                             │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │  STATE 6: SaveToDynamoDB (DynamoDB PutItem)                    │       │
│   │  ──────────────────────────────────────────                    │       │
│   │  • Saves to: ai-soc-dev-state table                            │       │
│   │  • Primary Key: alert_id + timestamp                           │       │
│   │  • Stored fields:                                              │       │
│   │    - alert_id (String)                                         │       │
│   │    - timestamp (String)                                        │       │
│   │    - priority_score (Number) → 75.3                            │       │
│   │    - priority_level (String) → "HIGH"                          │       │
│   │    - threat_score (Number) → 85.5                              │       │
│   │    - event_data (String) → Full JSON with all details          │       │
│   │                                                                 │       │
│   │  Duration: ~100-300ms                                          │       │
│   └───────────────────────────┬────────────────────────────────────┘       │
│                               │                                             │
│                               │ Item saved successfully                     │
│                               ▼                                             │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │  WORKFLOW COMPLETE                                             │       │
│   │  Status: SUCCEEDED                                             │       │
│   │  Total Duration: ~6-12 seconds                                 │       │
│   └────────────────────────────────────────────────────────────────┘       │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   │ Event now in DynamoDB
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DASHBOARD DISPLAY                                   │
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │  Browser requests:                                             │       │
│   │  http://ai-soc-dev-dashboard-194561596031.s3-website...        │       │
│   └───────────────────────────┬────────────────────────────────────┘       │
│                               │                                             │
│                               │ HTML/JS loaded from S3                      │
│                               ▼                                             │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │  JavaScript calls API:                                         │       │
│   │  GET https://rstevhgym8.execute-api.eu-central-1.../threats   │       │
│   └───────────────────────────┬────────────────────────────────────┘       │
│                               │                                             │
│                               │ API Gateway routes to Lambda                │
│                               ▼                                             │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │  Dashboard API Lambda                                          │       │
│   │  ────────────────────────                                      │       │
│   │  • Scans DynamoDB table (limit 50)                             │       │
│   │  • Parses event_data JSON strings                              │       │
│   │  • Converts numbers from strings to floats                     │       │
│   │  • Sorts by priority_score (highest first)                     │       │
│   │  • Returns JSON array of threats                               │       │
│   │                                                                 │       │
│   │  Duration: ~200-500ms                                          │       │
│   └───────────────────────────┬────────────────────────────────────┘       │
│                               │                                             │
│                               │ Returns: { success: true, count: 14,        │
│                               │           threats: [...] }                  │
│                               ▼                                             │
│   ┌────────────────────────────────────────────────────────────────┐       │
│   │  Browser renders threat cards                                  │       │
│   │  ────────────────────────────                                  │       │
│   │  For our traced event:                                         │       │
│   │                                                                 │       │
│   │  ┌──────────────────────────────────────────────┐              │       │
│   │  │ 🚨 trace-1765297166                          │              │       │
│   │  │                                              │              │       │
│   │  │ Priority: 75.3  |  HIGH                     │              │       │
│   │  │ Threat Score: 85.5                          │              │       │
│   │  │ Source: aws.guardduty                       │              │       │
│   │  │                                              │              │       │
│   │  │ AI Analysis:                                │              │       │
│   │  │  Risk: 8/10                                 │              │       │
│   │  │  Attack Vector: Unauthorized access from    │              │       │
│   │  │                 malicious IP address...     │              │       │
│   │  │  Actions: Investigate, Monitor, Notify      │              │       │
│   │  └──────────────────────────────────────────────┘              │       │
│   │                                                                 │       │
│   │  • Color-coded by severity (orange for HIGH)                   │       │
│   │  • Expandable to show full details                             │       │
│   │  • Live updates every 30 seconds                               │       │
│   └────────────────────────────────────────────────────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Timing Breakdown - Production Flow

**Total Journey: ~8-15 seconds** from AWS service detection to dashboard visibility

| Stage | Duration | Details |
|-------|----------|---------|
| **STAGE 1:** Event Detection | Varies | GuardDuty/Security Hub detects threat |
| **STAGE 2:** EventBridge Routing | ~50-100ms | Matches rules and triggers Lambda |
| **STAGE 3:** Event Normalizer | ~200-500ms | Standardizes event format |
| **STAGE 4:** Kinesis Buffering | ~100ms | Event queued in stream |
| **STAGE 5:** ML Inference | ~500ms-1s | Calculates threat score |
| **STAGE 6:** Step Functions Start | ~200ms | Workflow initialization |
| **STAGE 7:** Alert Triage | ~500ms | Lambda calculates priority |
| **STAGE 8:** Bedrock Analysis | 5-10s | AI processes event (longest step) |
| **STAGE 9:** SNS Notification | ~200ms | Publishes alert |
| **STAGE 10:** DynamoDB Save | ~300ms | Stores to database |
| **STAGE 11:** Dashboard API Call | ~500ms | Retrieves and formats data |
| **STAGE 12:** Browser Render | <100ms | Displays on screen |

### Fast Path (Low Priority Events)
Events with priority ≤ 70 skip Bedrock Analysis:
- **Total Time:** ~3-5 seconds from detection to dashboard

## Data Transformations - Production Flow

### 1. Raw GuardDuty Event (from AWS Service)
```json
{
  "version": "0",
  "id": "abc123-def456",
  "detail-type": "GuardDuty Finding",
  "source": "aws.guardduty",
  "account": "194561596031",
  "time": "2025-12-09T16:19:26Z",
  "region": "eu-central-1",
  "detail": {
    "schemaVersion": "2.0",
    "accountId": "194561596031",
    "region": "eu-central-1",
    "id": "gd-finding-123",
    "type": "UnauthorizedAccess:IAMUser/MaliciousIPCaller",
    "severity": 7.5,
    "title": "API call from malicious IP",
    "description": "An API call was invoked from a known malicious IP address",
    "service": {
      "serviceName": "guardduty",
      "action": {
        "actionType": "AWS_API_CALL",
        "awsApiCallAction": {
          "api": "DescribeInstances",
          "callerType": "Remote IP",
          "remoteIpDetails": {
            "ipAddressV4": "203.0.113.42",
            "country": { "countryName": "Russia" }
          }
        }
      }
    }
  }
}
```

### 2. After Event Normalizer (Standardized Format)
```json
{
  "event_id": "gd-finding-123",
  "timestamp": "2025-12-09T16:19:26Z",
  "source": "aws.guardduty",
  "account_id": "194561596031",
  "region": "eu-central-1",
  "event_type": "GuardDuty Finding",
  "severity": "HIGH",
  "raw_event": {
    "type": "UnauthorizedAccess:IAMUser/MaliciousIPCaller",
    "title": "API call from malicious IP",
    "description": "An API call was invoked from a known malicious IP address",
    "severity_score": 7.5,
    "service": "guardduty",
    "action_type": "AWS_API_CALL",
    "api": "DescribeInstances",
    "remote_ip": "203.0.113.42",
    "country": "Russia"
  }
}
```

### 3. After ML Inference (Threat Score Added)
```json
{
  ...previous fields...,
  "ml_prediction": {
    "threat_score": 85.5,
    "model_version": "1.0",
    "evaluated_at": "2025-12-09T16:19:26Z"
  }
}
```

### 4. After Alert Triage
```json
{
  ...previous fields...,
  "triage": {
    "priority_score": 75.3,
    "priority_level": "HIGH",
    "requires_human_review": true,
    "auto_remediate": false,
    "recommended_actions": ["INVESTIGATE", "MONITOR_CLOSELY", "NOTIFY_SECURITY_TEAM"]
  }
}
```

### 5. After Bedrock AI Analysis
```json
{
  ...previous fields...,
  "bedrock_analysis": {
    "risk_score": 8,
    "attack_vector": "Unauthorized API access from known malicious IP",
    "recommended_actions": ["Block IP", "Review access logs", "Rotate credentials"],
    "business_impact": "Potential data exfiltration",
    "confidence_level": 0.85
  }
}
```

### 6. Stored in DynamoDB
```json
{
  "alert_id": "trace-1765297166",
  "timestamp": "2025-12-09T16:26:06Z",
  "priority_score": 75.3,
  "threat_score": 85.5,
  "priority_level": "HIGH",
  "event_data": "{...full JSON string of all above data...}"
}
```

### 7. Dashboard API Response (Final Display Format)
```json
{
  "success": true,
  "count": 14,
  "threats": [
    {
      "alert_id": "trace-1765297166",
      "priority_score": 75.3,
      "threat_score": 85.5,
      "severity": "HIGH",
      "event_type": "GuardDuty Finding",
      "source": "aws.guardduty",
      "triage": { ... },
      "bedrock_analysis": { ... }
    }
  ]
}
```

## Key Decision Points

### 1. Priority Threshold (Line 70)
```
IF priority_score > 70 → Bedrock Analysis
ELSE → Log and skip AI analysis
```

### 2. Auto-Remediation Threshold (Line 90)
```
IF priority_score > 90 → Automatic remediation
ELSE → Notify security team only
```

### 3. Human Review Flag
```
IF priority_score > 80 → requires_human_review = true
```

## Production Data Flow Summary

```
GuardDuty Finding (Raw AWS Format)
    ↓
EventBridge (Routes by source pattern)
    ↓
Event Normalizer Lambda (Standardizes format)
    ↓
Kinesis Stream (Buffers events)
## End-to-End Verification Commands

```bash
# 1. Check GuardDuty is generating findings
aws guardduty list-findings \
  --detector-id $(aws guardduty list-detectors --query 'DetectorIds[0]' --output text) \
  --max-results 10 \
  --region eu-central-1

# 2. Verify EventBridge rules are active
aws events list-rules \
  --name-prefix ai-soc-dev \
  --region eu-central-1

# 3. Check Kinesis stream status
aws kinesis describe-stream \
  --stream-name ai-soc-dev-security-events \
  --region eu-central-1
## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| No events appearing | GuardDuty/Security Hub not enabled | Enable services in AWS Console |
| EventBridge not triggering | Rules misconfigured or disabled | Check rule patterns and state |
| Events stuck in Kinesis | ML Inference Lambda not consuming | Check Lambda errors in CloudWatch |
| Low threat scores | ML model needs training data | Normal for clean environments |
| Event not appearing in dashboard | Step Functions still processing | Wait 10-30 seconds |
| Missing AI analysis | Priority too low (<70) | Expected for low-risk events |
| No SNS notification | SNS topic not subscribed | Confirm email subscription |
| Dashboard shows cached data | Browser cache | Hard refresh (Ctrl+Shift+R) |
| High AWS costs | Too many shards/over-provisioned | Review Kinesis shard count |

## Test Script vs Production Flow

### Test Script (What we demonstrated)
- **Purpose:** Simulate the complete flow without waiting for real threats
- **Entry Point:** Directly invokes Step Functions with pre-formatted event
- **Includes:** Simulated `ml_prediction.threat_score` for demo purposes
- **Speed:** Immediate (no waiting for detection)
- **Use Case:** Demos, testing, validation

### Production Flow (Real-world operation)
- **Purpose:** Monitor and respond to actual security threats
- **Entry Point:** GuardDuty/Security Hub detection
- **Processing:** Full pipeline from detection → normalization → ML → orchestration
- **Speed:** 8-15 seconds from detection to dashboard
- **Use Case:** Continuous security monitoring

**Key Difference:** Test scripts skip stages 1-5 and inject events directly into Step Functions. Production processes events through all 12 stages.

# 5. Check Step Functions executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:eu-central-1:194561596031:stateMachine:ai-soc-dev-soc-workflow \
  --max-results 10 \
  --region eu-central-1

# 6. Query DynamoDB for recent events
aws dynamodb scan \
  --table-name ai-soc-dev-state \
  --max-items 5 \
  --region eu-central-1

# 7. Test dashboard API
curl -s "https://rstevhgym8.execute-api.eu-central-1.amazonaws.com/threats" | jq '.threats[0:3]'
```
Each stage logs to CloudWatch:

1. **/aws/lambda/ai-soc-dev-event-normalizer** - Event normalization and Kinesis writes
2. **/aws/lambda/ai-soc-dev-ml-inference** - ML threat scoring
3. **/aws/lambda/ai-soc-dev-alert-triage** - Triage calculations
4. **/aws/lambda/ai-soc-dev-bedrock-analysis** - AI analysis results
5. **/aws/lambda/ai-soc-dev-remediation** - Remediation actions
6. **/aws/states/ai-soc-dev-soc-workflow** - Overall workflow execution
7. **/aws/lambda/ai-soc-dev-dashboard-api** - API access logs

### Observability Commands

```bash
# Monitor EventBridge rule invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Events \
  --metric-name TriggeredRules \
  --dimensions Name=RuleName,Value=ai-soc-dev-guardduty-findings \
  --start-time 2025-12-09T00:00:00Z \
  --end-time 2025-12-09T23:59:59Z \
  --period 3600 \
  --statistics Sum

# Check Kinesis stream metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Kinesis \
  --metric-name IncomingRecords \
  --dimensions Name=StreamName,Value=ai-soc-dev-security-events \
  --start-time 2025-12-09T00:00:00Z \
  --end-time 2025-12-09T23:59:59Z \
  --period 300 \
  --statistics Sum

# View recent Event Normalizer logs
aws logs tail /aws/lambda/ai-soc-dev-event-normalizer --follow

# View ML Inference logs
aws logs tail /aws/lambda/ai-soc-dev-ml-inference --follow
```

## Verification Commands

```bash
# Check if event reached DynamoDB
aws dynamodb get-item \
  --table-name ai-soc-dev-state \
  --key '{"alert_id": {"S": "trace-1765297166"}, "timestamp": {"S": "2025-12-09T16:26:06Z"}}' \
  --region eu-central-1

# Check Step Functions execution
aws stepfunctions describe-execution \
  --execution-arn arn:aws:states:eu-central-1:194561596031:execution:ai-soc-dev-soc-workflow:trace-trace-1765297166 \
  --region eu-central-1

# Test dashboard API
curl -s "https://rstevhgym8.execute-api.eu-central-1.amazonaws.com/threats" | jq '.threats[] | select(.alert_id == "trace-1765297166")'
```

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Event not appearing | Step Functions still processing | Wait 10-30 seconds |
| 500 Error in API | Float conversion issue | Fixed in latest deployment |
| Missing AI analysis | Priority too low (<70) | Inject higher severity event |
| No SNS notification | SNS not subscribed | Confirm email subscription |
| Dashboard shows cached data | Browser cache | Hard refresh (Ctrl+Shift+R) |
