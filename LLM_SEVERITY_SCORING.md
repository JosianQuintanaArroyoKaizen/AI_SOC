# LLM-Based Severity Scoring

## Problem

Currently, all CloudTrail events default to `MEDIUM` severity because CloudTrail doesn't provide severity scores like GuardDuty or SecurityHub. This results in:
- No differentiation between normal operations and suspicious activity
- Everything appearing as MEDIUM in the dashboard
- Poor signal-to-noise ratio for security analysts

## Solution

Use **Claude Sonnet 3.5** to intelligently score CloudTrail events on a 0-10 scale based on:
- **Action Impact**: What resources are affected? Data access? Permission changes?
- **User Identity**: Root account? IAM user? Service role?
- **Access Patterns**: Unusual timing? Failed attempts?
- **Known Attack Vectors**: MITRE ATT&CK techniques
- **Error Codes**: Access denied = potential reconnaissance

## Two Approaches

### 1. Pre-label Training Data (Recommended First)

Score your dataset with Claude to create labeled training data, then retrain your ML model:

```bash
# Score all events in your dataset
cd /home/jquintana-arroyo/git/AI_SOC
python3 scripts/score_cloudtrail_events.py

# This creates: datasets/aws_samples/shared_services_labeled.json
# With LLM-assigned severity scores for each event
```

**Benefits:**
- Better ML model training with accurate labels
- More nuanced severity distribution
- Faster real-time processing (ML only, no LLM calls)
- Lower cost (one-time scoring vs. per-event)

**Output:**
```json
{
  "eventName": "DescribeSchema",
  "eventSource": "schemas.amazonaws.com",
  "userIdentity": {...},
  "llm_severity_score": 2.0,
  "llm_severity": "LOW",
  "llm_reasoning": "Read-only describe operation with no security impact",
  "llm_risk_factors": ["read-only", "routine-operation"]
}
```

### 2. Real-Time LLM Scoring (Optional)

Add the severity-scorer Lambda to your pipeline for real-time Claude analysis:

**Architecture:**
```
EventBridge → event-normalizer → severity-scorer → ml-inference → triage → orchestration
                                     ↑
                                 Claude Sonnet
                                 (scores 0-10)
```

**Deployment Steps:**

1. **Package the Lambda:**
```bash
cd lambda/severity-scorer
zip -r ../../severity-scorer.zip index.py
```

2. **Upload to S3:**
```bash
aws s3 cp severity-scorer.zip s3://ai-soc-dev-artifacts-194561596031/lambda/
```

3. **Add to CloudFormation** (in `06-orchestration.yaml`):
```yaml
SeverityScorerLambda:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: !Sub '${ProjectName}-${Environment}-severity-scorer'
    Runtime: python3.11
    Handler: index.handler
    Role: !GetAtt SeverityScorerRole.Arn
    Timeout: 60
    MemorySize: 512
    Environment:
      Variables:
        AWS_REGION: !Ref AWS::Region
    Code:
      S3Bucket: !Sub '${ProjectName}-${Environment}-artifacts-194561596031'
      S3Key: lambda/severity-scorer.zip

SeverityScorerRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Principal:
            Service: lambda.amazonaws.com
          Action: sts:AssumeRole
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    Policies:
      - PolicyName: BedrockAccess
        PolicyDocument:
          Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - bedrock:InvokeModel
              Resource: 'arn:aws:bedrock:*::foundation-model/anthropic.claude*'
```

4. **Update Step Functions** workflow to include severity scorer:
```json
{
  "Comment": "AI-SOC Workflow",
  "StartAt": "NormalizeEvent",
  "States": {
    "NormalizeEvent": {...},
    "ScoreSeverity": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:ai-soc-dev-severity-scorer",
      "Next": "MLInference"
    },
    "MLInference": {...}
  }
}
```

## Severity Scoring Guidelines

Claude uses these criteria:

| Score | Severity | Examples |
|-------|----------|----------|
| 0-2 | **LOW** | Read-only operations (Describe*, List*, Get*), routine queries |
| 3-4 | **LOW-MEDIUM** | Standard changes, routine admin tasks |
| 5-6 | **MEDIUM** | Configuration changes, S3 bucket policies, IAM changes |
| 7-8 | **HIGH** | Privilege escalation, credential creation, suspicious patterns |
| 9-10 | **CRITICAL** | Security logging disabled, root account usage, data exfiltration |

## Cost Considerations

**Pre-labeling (Recommended):**
- 2,200 events × $0.003/1K tokens ≈ **$5-10** one-time
- Faster real-time processing
- Better ML model

**Real-time scoring:**
- Per-event cost: ~$0.003/event
- 1,000 events/day = **$3/day = $90/month**
- Higher latency (60s timeout needed)

**Recommendation:** Pre-label your data first, retrain the model, then optionally add real-time scoring for ongoing events.

## Run the Pre-Labeling

```bash
cd /home/jquintana-arroyo/git/AI_SOC

# Install required package if needed
pip install tqdm

# Score all events (takes ~10-15 minutes for 2,200 events)
python3 scripts/score_cloudtrail_events.py
```

**Expected Output:**
```
🤖 CloudTrail Event Severity Scorer
============================================================

📂 Loading events from: datasets/aws_samples/shared_services.json
✅ Loaded 2,200 events

🔍 Scoring events with Claude Sonnet...
   Model: anthropic.claude-3-5-sonnet-20241022-v2:0
   Batch size: 10

Scoring: 100%|████████████████████████| 2200/2200 [12:34<00:00]

💾 Saving labeled dataset to: datasets/aws_samples/shared_services_labeled.json

============================================================
📊 Severity Distribution:
============================================================
CRITICAL       45 (  2.0%) ██
HIGH          182 (  8.3%) ████
MEDIUM        920 ( 41.8%) ████████████████████
LOW         1,053 ( 47.9%) ███████████████████████

✅ Complete! Labeled dataset saved
📈 Use this labeled data to retrain your ML model
```

## Next Steps After Labeling

1. **Update training script** to use labeled data:
```python
# In ml_training/train_cloudtrail_model.py
data_file = 'datasets/aws_samples/shared_services_labeled.json'

# Use llm_severity as ground truth label
X_train, X_test, y_train, y_test = train_test_split(
    features, 
    df['llm_severity'],  # Use LLM-labeled severity
    test_size=0.2
)
```

2. **Retrain the model** with better labels
3. **Deploy updated model** to SageMaker
4. **Enjoy better severity classification** in your dashboard! 🎯

## Questions?

- **Why not just use the LLM in production?** Cost and latency. ML is faster and cheaper for real-time.
- **Can I use both?** Yes! Pre-label for training, then optionally add real-time LLM for ongoing events.
- **What about false positives?** Claude is calibrated conservatively. You can adjust scoring in the script.
