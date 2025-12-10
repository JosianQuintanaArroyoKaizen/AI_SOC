# Production Deployment Guide

## Deploying AI-SOC to Your Production Account

### Prerequisites Checklist

#### 1. AWS Services Enablement
Ensure these services are enabled in the target account:

```bash
# Enable GuardDuty (if not already enabled)
aws guardduty create-detector --enable --region eu-central-1

# Enable Security Hub (if not already enabled)
aws securityhub enable-security-hub --region eu-central-1

# Verify they're enabled
aws guardduty list-detectors --region eu-central-1
aws securityhub describe-hub --region eu-central-1
```

#### 2. IAM Permissions
Your deployment role/user needs:
- CloudFormation full access
- Lambda, Step Functions, DynamoDB, Kinesis, EventBridge permissions
- S3 access for dashboard hosting
- IAM role creation permissions
- Bedrock access (for AI analysis)

#### 3. Service Quotas
Check you have sufficient quotas for:
- Lambda concurrent executions
- Step Functions executions
- DynamoDB capacity
- Kinesis shards

### Deployment Steps

#### Step 1: Configure Parameters
Edit `cloudformation/parameters/prod.json`:

```json
[
  {
    "ParameterKey": "ProjectName",
    "ParameterValue": "ai-soc"
  },
  {
    "ParameterKey": "Environment",
    "ParameterValue": "prod"
  },
  {
    "ParameterKey": "AlertEmail",
    "ParameterValue": "security-team@yourcompany.com"
  },
  {
    "ParameterKey": "KinesisShardCount",
    "ParameterValue": "2"
  }
]
```

#### Step 2: Deploy Infrastructure

```bash
# Deploy to production account
aws cloudformation deploy \
  --template-file cloudformation/root-stack.yaml \
  --stack-name ai-soc-prod \
  --parameter-overrides file://cloudformation/parameters/prod.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-central-1

# Monitor deployment
aws cloudformation describe-stack-events \
  --stack-name ai-soc-prod \
  --region eu-central-1 \
  --max-items 20
```

#### Step 3: Deploy Lambda Functions

```bash
# Package and deploy all Lambda functions
./scripts/deploy_lambdas.sh prod eu-central-1
```

#### Step 4: Verify Deployment

```bash
python3 scripts/verify_infrastructure.py
```

#### Step 5: Test with Synthetic Events

```bash
# Inject a few test events to verify the pipeline
python3 scripts/inject_test_events.py --count 5
```

### Monitoring Real Events

Once deployed to production, real events will flow through the pipeline:

**Expected Event Volume:**
- **Low activity accounts:** 5-20 events/day
- **Medium activity accounts:** 50-200 events/day  
- **High activity accounts:** 500+ events/day

**Common Real-World Triggers:**
- Failed login attempts
- IAM policy changes
- Security group modifications
- S3 bucket configuration changes
- Unusual API activity
- EC2 instance launches from unknown IPs
- Database access from unusual locations

### Multi-Account Setup (Advanced)

For organizations with multiple AWS accounts:

#### Option A: Central Monitoring Account
Deploy AI-SOC in a security/monitoring account and aggregate events from all accounts:

```bash
# In each member account, enable GuardDuty/SecurityHub
# Configure them to send findings to the central account

# In central account, deploy AI-SOC
# It will receive aggregated findings from all accounts
```

#### Option B: Per-Account Deployment
Deploy AI-SOC to each critical account separately:
- Better isolation
- Account-specific response actions
- More granular control

### Cost Considerations

**Production costs (estimated for medium activity account):**
- GuardDuty: ~$50-100/month
- Security Hub: ~$10-20/month
- Lambda: ~$5-15/month
- Step Functions: ~$5-10/month
- DynamoDB: ~$5-10/month
- Kinesis: ~$15-30/month
- Bedrock (Claude): ~$20-50/month (depends on volume)
- **Total: ~$110-235/month**

### Security Considerations

#### 1. Least Privilege IAM
- Review all IAM roles created by CloudFormation
- Ensure remediation Lambda has appropriate limited permissions
- Enable CloudTrail logging for all AI-SOC actions

#### 2. Data Retention
- DynamoDB TTL is set for automatic cleanup
- Configure appropriate retention for CloudWatch Logs
- Consider compliance requirements (GDPR, SOC2, etc.)

#### 3. Alert Routing
- Configure SNS topics for security team notifications
- Set up PagerDuty/Slack integration for critical alerts
- Define escalation procedures

#### 4. Bedrock Access
- Bedrock is used for high-priority threat analysis
- Review data sent to Bedrock for sensitive information
- Consider using AWS PrivateLink for Bedrock

### Rollback Plan

If issues occur:

```bash
# Delete the stack (preserves DynamoDB data if retention is configured)
aws cloudformation delete-stack \
  --stack-name ai-soc-prod \
  --region eu-central-1

# Or disable specific components
aws events disable-rule \
  --name ai-soc-prod-guardduty-findings \
  --region eu-central-1
```

### Post-Deployment Checklist

- [ ] GuardDuty enabled and generating findings
- [ ] Security Hub enabled and aggregating findings
- [ ] EventBridge rules active and routing events
- [ ] Lambda functions executing successfully
- [ ] Step Functions workflow processing events
- [ ] DynamoDB receiving threat data
- [ ] Dashboard accessible and displaying events
- [ ] SNS notifications being delivered
- [ ] CloudWatch alarms configured
- [ ] Team trained on dashboard usage
- [ ] Incident response procedures documented
- [ ] Cost monitoring alerts configured

### Troubleshooting

**No events appearing:**
1. Check GuardDuty/Security Hub are generating findings
2. Verify EventBridge rules are enabled
3. Check Lambda execution logs in CloudWatch
4. Review IAM permissions

**High costs:**
1. Review Kinesis shard count (reduce if over-provisioned)
2. Check Bedrock usage (only high-priority events should trigger)
3. Verify DynamoDB TTL is cleaning up old data
4. Review Lambda memory allocation

**Remediation failures:**
1. Check Lambda IAM permissions
2. Review CloudWatch logs for specific errors
3. Ensure resource tags/conditions are correct

### Support and Maintenance

**Regular maintenance tasks:**
- Weekly: Review dashboard for trends
- Monthly: Audit remediation actions
- Quarterly: Review and update threat models
- Annually: Re-evaluate architecture and costs

**Updates:**
```bash
# Update Lambda functions
./scripts/deploy_lambdas.sh prod eu-central-1

# Update infrastructure
aws cloudformation update-stack \
  --stack-name ai-soc-prod \
  --template-body file://cloudformation/root-stack.yaml \
  --parameters file://cloudformation/parameters/prod.json \
  --capabilities CAPABILITY_NAMED_IAM
```
