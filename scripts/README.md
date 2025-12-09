# AI-SOC Testing Scripts

## inject_test_events.py

Inject realistic test security events into your AI-SOC pipeline to demonstrate the complete flow from event generation to DynamoDB storage.

### Prerequisites

```bash
# Ensure you have AWS credentials configured
aws configure

# Install dependencies (if not already installed)
pip3 install boto3
```

### Usage Examples

**Inject 5 random mixed events (GuardDuty + Security Hub):**
```bash
python3 scripts/inject_test_events.py --count 5
```

**Inject 10 high-severity events:**
```bash
python3 scripts/inject_test_events.py --count 10 --severity HIGH
```

**Inject only GuardDuty events:**
```bash
python3 scripts/inject_test_events.py --count 5 --source guardduty
```

**Inject critical Security Hub events:**
```bash
python3 scripts/inject_test_events.py --count 3 --source securityhub --severity CRITICAL
```

**Try both EventBridge and Step Functions methods:**
```bash
python3 scripts/inject_test_events.py --count 5 --method both
```

### How It Works

The script creates realistic test events that simulate:

**GuardDuty Findings:**
- Unauthorized access from malicious IPs
- Port scanning and reconnaissance
- Trojan/backdoor activity
- Cryptocurrency mining
- Command & Control communications

**Security Hub Findings:**
- IAM policy violations
- S3 bucket misconfigurations
- Security group issues

### Injection Methods

1. **Step Functions (Default)** - Directly starts the orchestration workflow
   - Faster for testing
   - Bypasses event normalization
   - Includes mock ML scores

2. **EventBridge** - Sends events through the full pipeline
   - Tests the complete flow
   - Requires EventBridge rules to be active
   - More realistic simulation

3. **Both** - Tries EventBridge first, falls back to Step Functions

### Viewing Results

After injection, check:

1. **Dashboard:** http://localhost:5000
2. **DynamoDB Console:** `ai-soc-dev-state` table
3. **Step Functions Console:** Check execution history
4. **CloudWatch Logs:** Lambda function logs

Events should appear in DynamoDB within 10-30 seconds.

### Troubleshooting

**No events appearing in DynamoDB?**
- Check Step Functions execution in AWS Console
- Verify Lambda function permissions
- Check CloudWatch Logs for errors
- Ensure your AWS credentials have the necessary permissions

**Permission errors?**
- Ensure your IAM user/role has permissions to:
  - Execute Step Functions
  - Put events to EventBridge
  - Read DynamoDB (for the dashboard)

### Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--count` | Integer | 5 | Number of events to generate |
| `--severity` | LOW, MEDIUM, HIGH, CRITICAL | Random | Override severity |
| `--method` | eventbridge, stepfunctions, both | stepfunctions | Injection method |
| `--source` | guardduty, securityhub, mixed | mixed | Event source type |
