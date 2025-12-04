# AWS Serverless Autonomous SOC - Implementation Guide

> **Authoritative Reference**: Use this guide first for every AWS/AI deployment decision. All stacks, pipelines, and supporting services must launch in `eu-central-1` using AWS CloudFormation orchestrated through CI/CD.

## Executive Summary

This guide provides a complete roadmap for building a **serverless, scalable, autonomous Security Operations Center (SOC)** on AWS, adapting concepts from the open-source AI_SOC project to create a cloud-native, cost-effective security platform with agentic AI capabilities.

**Project Goal**: Deploy Infrastructure as Code (IaC) to create an autonomous SOC that can handle security events with minimal human intervention.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Source Repository](#source-repository)
3. [What We're Building](#what-were-building)
4. [Architecture](#architecture)
5. [Prerequisites](#prerequisites)
6. [AWS Serverless Adaptation Strategy](#aws-serverless-adaptation-strategy)
7. [Implementation Phases](#implementation-phases)
8. [Phase 1: Infrastructure Setup](#phase-1-infrastructure-setup)
9. [Phase 2: Simple Use Case](#phase-2-simple-use-case)
10. [Cost Estimates](#cost-estimates)
11. [Next Steps](#next-steps)

---

## Project Overview

### What is an Autonomous SOC?

An **Autonomous Security Operations Center** uses agentic AI to:
- **Detect** security threats automatically
- **Analyze** alerts with machine learning
- **Triage** incidents by priority without human input
- **Respond** to threats autonomously based on predefined policies
- **Learn** and adapt over time

### Key Principles

- ✅ **Serverless**: No servers to manage, pay only for what you use
- ✅ **Scalable**: Automatically handles 10 to 10,000+ events per day
- ✅ **Event-Driven**: Processes events as they occur, not continuously
- ✅ **Cost-Effective**: Scales to zero during low activity
- ✅ **Infrastructure as Code**: Everything deployed via AWS CloudFormation (CI/CD-driven)

---

## Source Repository

### Base Project: AI_SOC by zhadyz
### What We're Using From It

We're extracting the **concepts and AI/ML components**, but **NOT** using the Docker Compose infrastructure:

| Component | Original (Docker) | Our AWS Adaptation |
|-----------|------------------|-------------------|
| **SIEM Core** | Wazuh (containers) | AWS Security Services + Lambda |
| **Data Storage** | OpenSearch (container) | Amazon OpenSearch Serverless |
| **ML Inference** | FastAPI container | AWS Lambda + SageMaker Serverless |
| **Alert Triage** | Python service | AWS Lambda function |
| **RAG Service** | ChromaDB container | Amazon Bedrock Knowledge Base |
| **Vector DB** | ChromaDB | OpenSearch vector engine |
| **Orchestration** | Docker Compose | AWS Step Functions |

### Key Concepts We're Adapting

1. **ML-based threat detection** (99.28% accuracy on CICIDS2017 dataset)
2. **Intelligent alert triage** with severity scoring
3. **RAG-enhanced threat intelligence** using MITRE ATT&CK
4. **Autonomous decision-making** with minimal human oversight

---

## What We're Building

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   AWS SECURITY DATA SOURCES                      │
├─────────────────────────────────────────────────────────────────┤
│  CloudTrail  │  GuardDuty  │  VPC Flow Logs  │  Security Hub   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      EVENT INGESTION                             │
├─────────────────────────────────────────────────────────────────┤
│           EventBridge → Lambda (Normalization)                   │
│                  Kinesis Data Streams                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    AI/ML PROCESSING                              │
├─────────────────────────────────────────────────────────────────┤
│  SageMaker Serverless Inference → Threat Detection ML Models    │
│  Lambda → Alert Triage Logic                                    │
│  Amazon Bedrock → Agentic AI (RAG + Decision Making)           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    STORAGE & SEARCH                              │
├─────────────────────────────────────────────────────────────────┤
│  OpenSearch Serverless → Alert Storage & Visualization          │
│  S3 → Raw Logs & ML Model Artifacts                            │
│  DynamoDB → State Management                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  AUTONOMOUS RESPONSE                             │
├─────────────────────────────────────────────────────────────────┤
│  Step Functions → Workflow Orchestration                         │
│  Lambda → Automated Remediation                                  │
│  SNS → Alerting (when escalation needed)                        │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

1. **Event Ingestion Pipeline**
   - Collects security events from AWS services
   - Normalizes data format
   - Routes to processing pipeline

2. **ML Threat Detection**
   - Uses trained models for threat classification
   - Serverless inference (scales automatically)
   - 99%+ accuracy on known attack patterns

3. **Intelligent Alert Triage**
   - Scores alerts by severity and confidence
   - Reduces false positives
   - Prioritizes critical threats

4. **Agentic AI Analysis**
   - Uses Amazon Bedrock for autonomous reasoning
   - RAG with MITRE ATT&CK knowledge base
   - Makes response decisions automatically

5. **Automated Response**
   - Step Functions orchestrate workflows
   - Lambda executes remediation actions
   - SNS escalates when needed

---

## Architecture

### Detailed Component Diagram

```
                    ┌──────────────────────┐
                    │   Security Events    │
                    │  (CloudTrail, etc.)  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    EventBridge       │
                    │  (Event Routing)     │
                    └──────────┬───────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ Lambda   │   │ Lambda   │   │ Lambda   │
        │Normalize │   │Enrich    │   │Filter    │
        └─────┬────┘   └─────┬────┘   └─────┬────┘
              └──────────────┼──────────────┘
                             ▼
                  ┌─────────────────────┐
                  │  Kinesis Stream     │
                  │ (Event Buffering)   │
                  └──────────┬──────────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │SageMaker │  │  Lambda  │  │ Bedrock  │
        │Serverless│  │  Triage  │  │  Agent   │
        │Inference │  │  Logic   │  │   RAG    │
        └─────┬────┘  └─────┬────┘  └─────┬────┘
              └────────────┼──────────────┘
                           ▼
              ┌─────────────────────────┐
              │  Step Functions         │
              │ (Workflow Orchestration)│
              └─────────┬───────────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │OpenSearch│  │  Lambda  │  │   SNS    │
  │Serverless│  │Remediate │  │  Alert   │
  └──────────┘  └──────────┘  └──────────┘
```

### Data Flow

1. **Security Event** occurs (e.g., GuardDuty finding)
2. **EventBridge** receives event and routes to Lambda
3. **Lambda** normalizes event format
4. **Kinesis** buffers events for batch processing
5. **SageMaker** performs ML inference (threat detection)
6. **Lambda** performs alert triage (scoring)
7. **Bedrock Agent** analyzes with RAG (context from MITRE)
8. **Step Functions** orchestrates response workflow
9. **Lambda** executes automated remediation
10. **OpenSearch** stores for investigation
11. **SNS** notifies if escalation needed

---

## Prerequisites

### AWS Account Requirements

 AWS Account with appropriate permissions
 AWS CLI configured with credentials
 Region: `eu-central-1` (all resources, including Bedrock, should be deployed here)

### Local Development Environment (optional authoring support)

```bash
# Required tools
- AWS CLI >= 2.13.0
- AWS SAM CLI or cfn-lint (for template validation)
- Python >= 3.10
- Git
- jq (for JSON parsing)
```

### Installation Commands

```bash
# macOS
brew install awscli aws-sam-cli python@3.10 jq

# Ubuntu/Debian
sudo apt update
sudo apt install -y awscli python3.10 jq
pip install aws-sam-cli --break-system-packages

# Verify installations
aws --version
sam --version
python3 --version
```

### AWS Permissions Required

Your IAM user/role needs permissions for:
- Lambda (create, update, invoke)
- OpenSearch Serverless
- SageMaker
- Bedrock
- EventBridge
- Step Functions
- S3
- CloudFormation (create/change/delete stacks)
- IAM (create roles)
- CloudWatch Logs

**Recommended**: Use AdministratorAccess for POC, restrict later for production.

---

## AWS Serverless Adaptation Strategy

### Why Serverless?

| Traditional (Containers) | Serverless |
|-------------------------|------------|
| Always running = always paying | Pay per use |
| Manual scaling | Auto-scales |
| Server maintenance | Zero maintenance |
| Fixed capacity | Unlimited scale |
| $500+/month minimum | $50-300/month typical |

### Key Serverless Services We're Using

#### 1. AWS Lambda
- **Purpose**: Event processing, ML inference execution, alert triage
- **Pricing**: $0.20 per 1M requests + compute time
- **Scales**: 0 to 10,000+ concurrent executions

#### 2. Amazon OpenSearch Serverless
- **Purpose**: Alert storage, search, visualization
- **Pricing**: Pay per OCU (OpenSearch Compute Unit)
- **Scales**: Automatically adjusts capacity

#### 3. Amazon SageMaker Serverless Inference
- **Purpose**: ML model hosting for threat detection
- **Pricing**: Pay per inference + compute time
- **Scales**: To zero when idle

#### 4. Amazon Bedrock
- **Purpose**: Agentic AI for autonomous decision-making
- **Pricing**: Pay per token (input/output)
- **Scales**: Fully managed, unlimited

#### 5. AWS Step Functions
- **Purpose**: Orchestrate multi-step workflows
- **Pricing**: $0.025 per 1,000 state transitions
- **Scales**: Automatically

---

## Implementation Phases

### Phase 1: Infrastructure Setup (Week 1)
**Goal**: Deploy core AWS infrastructure with IaC

**Deliverables**:
- AWS CloudFormation templates (nested stacks) for core resources
- GitHub Actions workflow wiring for CI/CD-driven stack deployments
- Event ingestion pipeline (EventBridge → Lambda → Kinesis)
- OpenSearch Serverless for storage
- Basic Lambda functions packaged via CI artifacts

**Success Criteria**: Can ingest and store security events

---

### Phase 2: Simple Use Case (Week 2)
**Goal**: Implement one complete autonomous workflow

**Use Case**: Detect and respond to suspicious API calls

**Deliverables**:
- ML model for threat detection (artifact stored in S3, referenced by CloudFormation parameters)
- Alert triage logic packaged as Lambda artifact
- Automated response action wired through Step Functions via CloudFormation stack update
- Dashboard visualization backed by OpenSearch queries

**Success Criteria**: End-to-end autonomous detection and response

---

### Phase 3: Agentic AI Integration (Week 3)
**Goal**: Add Amazon Bedrock for intelligent decision-making

**Deliverables**:
- Bedrock agent configuration
- RAG with MITRE ATT&CK
- Multi-step reasoning workflows

---

### Phase 4: Production Hardening (Week 4)
**Goal**: Production-ready deployment

**Deliverables**:
- Security hardening
- Cost optimization
- Monitoring and alerting
- Documentation

---

## Phase 1: Infrastructure Setup

### Step 1: Repository & Template Layout

```text
cloudformation/
├── root-stack.yaml                # Parent template orchestrating nested stacks
├── nested/
│   ├── event-ingestion.yaml       # EventBridge, Lambda, Kinesis
│   ├── storage.yaml               # OpenSearch Serverless, S3, DynamoDB
│   ├── ml-inference.yaml          # SageMaker Serverless + permissions
│   ├── remediation.yaml           # Automated response Lambda(s)
│   ├── orchestration.yaml         # Step Functions + remediation Lambdas
│   └── iam.yaml                   # Centralized IAM roles/policies
├── parameters/
│   ├── dev.json
│   ├── staging.json
│   └── prod.json
└── metadata/
    └── mappings.yaml              # Optional account/region mappings

lambda/
├── event-normalizer/
├── alert-triage/
└── remediation/

.github/workflows/
├── lambda-build.yml
├── cfn-plan.yml
└── cfn-apply.yml
```

### Step 2: Root Stack Definition

**File: `cloudformation/root-stack.yaml`**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: AWS Serverless SOC - Root Stack (eu-central-1)
Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, staging, prod]
  ProjectName:
    Type: String
    Default: serverless-soc
  LambdaArtifactBucket:
    Type: String
  LambdaArtifactPrefix:
    Type: String
  ModelArtifactUri:
    Type: String
  AlertEmail:
    Type: String

Resources:
  EventIngestionStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: !Sub "https://s3.${AWS::Region}.amazonaws.com/${LambdaArtifactBucket}/templates/event-ingestion.yaml"
      Parameters:
        ProjectName: !Ref ProjectName
        Environment: !Ref Environment
        LambdaArtifactBucket: !Ref LambdaArtifactBucket
        LambdaArtifactPrefix: !Ref LambdaArtifactPrefix

  StorageStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: !Sub "https://s3.${AWS::Region}.amazonaws.com/${LambdaArtifactBucket}/templates/storage.yaml"
      Parameters:
        ProjectName: !Ref ProjectName
        Environment: !Ref Environment

  RemediationStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: !Sub "https://s3.${AWS::Region}.amazonaws.com/${LambdaArtifactBucket}/templates/remediation.yaml"
      Parameters:
        ProjectName: !Ref ProjectName
        Environment: !Ref Environment
        LambdaArtifactBucket: !Ref LambdaArtifactBucket
        LambdaArtifactPrefix: !Ref LambdaArtifactPrefix

  MlInferenceStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: !Sub "https://s3.${AWS::Region}.amazonaws.com/${LambdaArtifactBucket}/templates/ml-inference.yaml"
      Parameters:
        ProjectName: !Ref ProjectName
        Environment: !Ref Environment
        ModelArtifactUri: !Ref ModelArtifactUri
        LambdaArtifactBucket: !Ref LambdaArtifactBucket
        LambdaArtifactPrefix: !Ref LambdaArtifactPrefix

  OrchestrationStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: !Sub "https://s3.${AWS::Region}.amazonaws.com/${LambdaArtifactBucket}/templates/orchestration.yaml"
      Parameters:
        ProjectName: !Ref ProjectName
        Environment: !Ref Environment
        AlertEmail: !Ref AlertEmail
        MlFunctionArn: !GetAtt MlInferenceStack.Outputs.InferenceFunctionArn
        TriageFunctionArn: !GetAtt EventIngestionStack.Outputs.TriageFunctionArn
        RemediationFunctionArn: !GetAtt RemediationStack.Outputs.RemediationFunctionArn
        StateTableName: !GetAtt StorageStack.Outputs.StateTableName

Outputs:
  WorkflowArn:
    Description: Step Functions state machine ARN
    Value: !GetAtt OrchestrationStack.Outputs.WorkflowArn
```

### Step 3: Event Ingestion Nested Template

**File: `cloudformation/nested/event-ingestion.yaml`**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Event ingestion resources
Parameters:
  ProjectName:
    Type: String
  Environment:
    Type: String
  LambdaArtifactBucket:
    Type: String
  LambdaArtifactPrefix:
    Type: String

Resources:
  SecurityEventStream:
    Type: AWS::Kinesis::Stream
    Properties:
      Name: !Sub "${ProjectName}-${Environment}-security-events"
      RetentionPeriodHours: 24
      ShardCount: 1

  EventNormalizerLambda:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${ProjectName}-${Environment}-event-normalizer"
      Runtime: python3.11
      Handler: index.handler
      Code:
        S3Bucket: !Ref LambdaArtifactBucket
        S3Key: !Sub "${LambdaArtifactPrefix}/event-normalizer.zip"
      Timeout: 30
      MemorySize: 512
      Environment:
        Variables:
          KINESIS_STREAM_NAME: !Ref SecurityEventStream
      Role: !GetAtt EventNormalizerRole.Arn

  EventNormalizerRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: KinesisWrite
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - kinesis:PutRecord
                  - kinesis:PutRecords
                Resource: !GetAtt SecurityEventStream.Arn
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: arn:aws:logs:*:*:*

  GuardDutyRule:
    Type: AWS::Events::Rule
    Properties:
      Description: GuardDuty findings to Lambda
      EventPattern:
        source:
          - aws.guardduty
        detail-type:
          - GuardDuty Finding
      Targets:
        - Arn: !GetAtt EventNormalizerLambda.Arn
          Id: NormalizeGuardDuty

  AllowEventBridgeInvoke:
    Type: AWS::Lambda::Permission
    Properties:
      Action: lambda:InvokeFunction
      FunctionName: !GetAtt EventNormalizerLambda.Arn
      Principal: events.amazonaws.com
      SourceArn: !GetAtt GuardDutyRule.Arn

  AlertTriageRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: BasicLogging
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: arn:aws:logs:*:*:*

  AlertTriageLambda:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${ProjectName}-${Environment}-alert-triage"
      Runtime: python3.11
      Handler: index.handler
      Code:
        S3Bucket: !Ref LambdaArtifactBucket
        S3Key: !Sub "${LambdaArtifactPrefix}/alert-triage.zip"
      Timeout: 30
      MemorySize: 512
      Role: !GetAtt AlertTriageRole.Arn

Outputs:
  EventStreamArn:
    Value: !GetAtt SecurityEventStream.Arn
  EventNormalizerArn:
    Value: !GetAtt EventNormalizerLambda.Arn
  TriageFunctionArn:
    Value: !GetAtt AlertTriageLambda.Arn
```

### Step 4: Remediation Lambda Template

**File: `cloudformation/nested/remediation.yaml`**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Automated remediation Lambda functions
Parameters:
  ProjectName:
    Type: String
  Environment:
    Type: String
  LambdaArtifactBucket:
    Type: String
  LambdaArtifactPrefix:
    Type: String

Resources:
  RemediationRole:
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
        - arn:aws:iam::aws:policy/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: RemediationActions
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - iam:UpdateAccessKey
                  - iam:DeactivateMFADevice
                  - ec2:RevokeSecurityGroupIngress
                Resource: '*'

  RemediationLambda:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${ProjectName}-${Environment}-remediation"
      Runtime: python3.11
      Handler: index.handler
      Code:
        S3Bucket: !Ref LambdaArtifactBucket
        S3Key: !Sub "${LambdaArtifactPrefix}/remediation.zip"
      Timeout: 30
      MemorySize: 256
      Role: !GetAtt RemediationRole.Arn

Outputs:
  RemediationFunctionArn:
    Value: !GetAtt RemediationLambda.Arn
```

### Step 5: Storage & State Nested Template

**File: `cloudformation/nested/storage.yaml`**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Storage resources
Parameters:
  ProjectName:
    Type: String
  Environment:
    Type: String

Resources:
  SocDataBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub "${ProjectName}-${Environment}-data-${AWS::AccountId}"
      VersioningConfiguration:
        Status: Enabled
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256

  SocStateTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "${ProjectName}-${Environment}-state"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: alert_id
          AttributeType: S
      KeySchema:
        - AttributeName: alert_id
          KeyType: HASH
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true

  SocCollection:
    Type: AWS::OpenSearchServerless::Collection
    Properties:
      Name: !Sub "${ProjectName}-${Environment}-alerts"
      Type: SEARCH

  SocEncryptionPolicy:
    Type: AWS::OpenSearchServerless::SecurityPolicy
    Properties:
      Name: !Sub "${ProjectName}-${Environment}-encryption"
      Type: encryption
      Policy: !Sub |
        {
          "Rules": [{
            "Resource": ["collection/${ProjectName}-${Environment}-alerts"],
            "ResourceType": "collection"
          }],
          "AWSOwnedKey": true
        }

Outputs:
  DataBucketName:
    Value: !Ref SocDataBucket
  StateTableName:
    Value: !Ref SocStateTable
  OpenSearchCollectionArn:
    Value: !GetAtt SocCollection.Arn
```

### Step 6: Environment Parameters

Store CloudFormation parameters per environment inside `cloudformation/parameters`. Example `dev.json`:

```json
[
  { "ParameterKey": "Environment", "ParameterValue": "dev" },
  { "ParameterKey": "ProjectName", "ParameterValue": "serverless-soc" },
  { "ParameterKey": "LambdaArtifactBucket", "ParameterValue": "soc-artifacts-dev" },
  { "ParameterKey": "LambdaArtifactPrefix", "ParameterValue": "packages" },
  { "ParameterKey": "ModelArtifactUri", "ParameterValue": "s3://soc-artifacts-dev/ml-models/threat-detection.tar.gz" },
  { "ParameterKey": "AlertEmail", "ParameterValue": "dev-alerts@example.com" }
]
```

Upload templates to the artifact bucket (the CI pipeline automates this) so nested stacks resolve `TemplateURL` paths.

### Step 6: Lambda Function Code

**File: `lambda/event-normalizer/index.py`**

```python
import json
import boto3
import os
from datetime import datetime

kinesis = boto3.client('kinesis')
STREAM_NAME = os.environ['KINESIS_STREAM_NAME']

def handler(event, context):
    """
    Normalize security events from various AWS sources
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract source and detail
        source = event.get('source', 'unknown')
        detail = event.get('detail', {})
        
        # Normalize event structure
        normalized_event = {
            'event_id': event.get('id', 'unknown'),
            'timestamp': event.get('time', datetime.utcnow().isoformat()),
            'source': source,
            'account_id': event.get('account', 'unknown'),
            'region': event.get('region', 'unknown'),
            'event_type': event.get('detail-type', 'unknown'),
            'severity': extract_severity(detail, source),
            'raw_event': detail
        }
        
        # Send to Kinesis
        response = kinesis.put_record(
            StreamName=STREAM_NAME,
            Data=json.dumps(normalized_event),
            PartitionKey=normalized_event['event_id']
        )
        
        print(f"Event sent to Kinesis: {response['SequenceNumber']}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Event processed successfully'})
        }
        
    except Exception as e:
        print(f"Error processing event: {str(e)}")
        raise

def extract_severity(detail, source):
    """
    Extract severity from event based on source
    """
    severity_map = {
        'aws.guardduty': lambda d: d.get('severity', 0),
        'aws.securityhub': lambda d: d.get('Severity', {}).get('Normalized', 0)
    }
    
    extractor = severity_map.get(source, lambda d: 0)
    raw_severity = extractor(detail)
    
    # Normalize to LOW, MEDIUM, HIGH, CRITICAL
    if raw_severity >= 7:
        return 'CRITICAL'
    elif raw_severity >= 4:
        return 'HIGH'
    elif raw_severity >= 1:
        return 'MEDIUM'
    else:
        return 'LOW'
```

**File: `lambda/event-normalizer/requirements.txt`**

```
boto3>=1.28.0
```

### Step 7: Package Lambda Artifacts (CI/CD-first)

Artifact packaging is handled automatically inside `lambda-build.yml`. For ad-hoc local validation:

```bash
cd lambda/event-normalizer

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -t package/
cp *.py package/
cd package
zip -r ../../dist/event-normalizer.zip . -x "tests/*" "__pycache__/*"

# Optional: upload to artifact bucket for manual testing
aws s3 cp ../../dist/event-normalizer.zip s3://soc-artifacts-dev/packages/event-normalizer-latest.zip \
  --region eu-central-1
```

### Step 8: Deploy via CloudFormation Change Sets

CI/CD Workflow:
1. `lambda-build.yml` → builds artifacts, uploads to `soc-artifacts-<env>` bucket.
2. `cfn-plan.yml` → runs `cfn-lint`, creates a `ChangeSet` against `root-stack` using the environment parameter file.
3. `cfn-apply.yml` → executes the approved Change Set (dev auto, staging/prod require approvals).

Manual fallback (only when CI unavailable):

```bash
aws cloudformation package \
  --template-file cloudformation/root-stack.yaml \
  --s3-bucket soc-artifacts-dev \
  --s3-prefix templates \
  --region eu-central-1 \
  --output-template-file packaged-root.yaml

aws cloudformation deploy \
  --template-file packaged-root.yaml \
  --stack-name serverless-soc-dev \
  --parameter-overrides file://cloudformation/parameters/dev.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-central-1

aws cloudformation describe-stacks --stack-name serverless-soc-dev --region eu-central-1 \
  --query "Stacks[0].Outputs"
```

---

## Phase 2: Simple Use Case

### Use Case: Detect Suspicious API Calls

**Scenario**: Detect when an IAM role makes unusual API calls that could indicate compromise.

**Workflow**:
1. CloudTrail logs API call
2. EventBridge captures event
3. Lambda normalizes event
4. SageMaker ML model classifies threat (0-100 score)
5. Lambda triages alert (prioritize by score)
6. If score > 80: Bedrock agent analyzes with MITRE context
7. Step Functions orchestrates response
8. Lambda disables IAM credentials if confirmed threat
9. SNS notifies security team

### Implementation

**File: `cloudformation/nested/ml-inference.yaml`**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: ML inference resources (SageMaker + Lambda)
Parameters:
  ProjectName:
    Type: String
  Environment:
    Type: String
  ModelArtifactUri:
    Type: String
  LambdaArtifactBucket:
    Type: String
  LambdaArtifactPrefix:
    Type: String

Resources:
  ThreatDetectionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: sagemaker.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: AccessModelArtifacts
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - s3:GetObject
                Resource: !Sub "${ModelArtifactUri}*"

  ThreatDetectionModel:
    Type: AWS::SageMaker::Model
    Properties:
      ExecutionRoleArn: !GetAtt ThreatDetectionRole.Arn
      PrimaryContainer:
        Image: !Sub "763104351884.dkr.ecr.${AWS::Region}.amazonaws.com/sklearn-inference:1.2-1-cpu-py3"
        ModelDataUrl: !Ref ModelArtifactUri

  ThreatDetectionEndpointConfig:
    Type: AWS::SageMaker::EndpointConfig
    Properties:
      ProductionVariants:
        - VariantName: AllTraffic
          ModelName: !Ref ThreatDetectionModel
          ServerlessConfig:
            MaxConcurrency: 20
            MemorySizeInMB: 2048

  ThreatDetectionEndpoint:
    Type: AWS::SageMaker::Endpoint
    Properties:
      EndpointConfigName: !Ref ThreatDetectionEndpointConfig
      EndpointName: !Sub "${ProjectName}-${Environment}-threat-detection"

  MlInferenceLambdaRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: InvokeSageMaker
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - sagemaker:InvokeEndpoint
                Resource: !GetAtt ThreatDetectionEndpoint.EndpointArn
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: arn:aws:logs:*:*:*

  MlInferenceLambda:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${ProjectName}-${Environment}-ml-inference"
      Runtime: python3.11
      Handler: index.handler
      Code:
        S3Bucket: !Ref LambdaArtifactBucket
        S3Key: !Sub "${LambdaArtifactPrefix}/ml-inference.zip"
      Timeout: 60
      MemorySize: 1024
      Environment:
        Variables:
          SAGEMAKER_ENDPOINT: !Ref ThreatDetectionEndpoint
      Role: !GetAtt MlInferenceLambdaRole.Arn

Outputs:
  InferenceFunctionArn:
    Value: !GetAtt MlInferenceLambda.Arn
  EndpointName:
    Value: !Ref ThreatDetectionEndpoint
```

**File: `lambda/ml-inference/index.py`**

```python
import json
import boto3
import os

sagemaker_runtime = boto3.client('sagemaker-runtime')
ENDPOINT_NAME = os.environ['SAGEMAKER_ENDPOINT']

def handler(event, context):
    """
    Invoke SageMaker endpoint for threat detection
    """
    try:
        # Extract features from event
        features = extract_features(event)
        
        # Invoke SageMaker endpoint
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType='application/json',
            Body=json.dumps(features)
        )
        
        # Parse prediction
        result = json.loads(response['Body'].read().decode())
        threat_score = result['predictions'][0]
        
        # Add prediction to event
        event['ml_prediction'] = {
            'threat_score': float(threat_score),
            'model_version': '1.0',
            'confidence': 0.95
        }
        
        return event
        
    except Exception as e:
        print(f"Error in ML inference: {str(e)}")
        # Return event with error flag
        event['ml_prediction'] = {
            'threat_score': 0.0,
            'error': str(e)
        }
        return event

def extract_features(event):
    """
    Extract ML features from security event
    """
    raw_event = event.get('raw_event', {})
    
    # Example features (customize based on your model)
    features = {
        'api_call_count': 1,
        'error_rate': 0 if raw_event.get('errorCode') is None else 1,
        'source_ip_reputation': 0.5,  # Placeholder
        'time_of_day': get_hour_of_day(event['timestamp']),
        'user_history_score': 0.7,  # Placeholder
    }
    
    return features

def get_hour_of_day(timestamp):
    """Get hour from timestamp"""
    from datetime import datetime
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    return dt.hour
```

**File: `lambda/alert-triage/index.py`**

```python
import json
import os

def handler(event, context):
    """
    Triage alerts based on ML score and other factors
    """
    try:
        threat_score = event.get('ml_prediction', {}).get('threat_score', 0)
        severity = event.get('severity', 'LOW')
        source = event.get('source', 'unknown')
        
        # Calculate priority score (0-100)
        priority_score = calculate_priority(threat_score, severity, source)
        
        # Add triage information
        event['triage'] = {
            'priority_score': priority_score,
            'priority_level': get_priority_level(priority_score),
            'requires_human_review': priority_score > 80,
            'auto_remediate': priority_score > 90
        }
        
        print(f"Alert triaged: priority={priority_score}, level={get_priority_level(priority_score)}")
        
        return event
        
    except Exception as e:
        print(f"Error in triage: {str(e)}")
        event['triage'] = {'error': str(e)}
        return event

def calculate_priority(threat_score, severity, source):
    """
    Calculate priority score based on multiple factors
    """
    severity_weights = {
        'CRITICAL': 40,
        'HIGH': 30,
        'MEDIUM': 20,
        'LOW': 10
    }
    
    source_weights = {
        'aws.guardduty': 1.2,
        'aws.securityhub': 1.1,
        'aws.cloudtrail': 1.0
    }
    
    base_score = (threat_score * 0.6) + severity_weights.get(severity, 10)
    adjusted_score = base_score * source_weights.get(source, 1.0)
    
    return min(100, max(0, adjusted_score))

def get_priority_level(score):
    """Convert numeric score to priority level"""
    if score >= 90:
        return 'CRITICAL'
    elif score >= 70:
        return 'HIGH'
    elif score >= 40:
        return 'MEDIUM'
    else:
        return 'LOW'
```

### Step Functions Workflow

**File: `cloudformation/nested/orchestration.yaml`**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Orchestration stack (Step Functions + notifications)
Parameters:
  ProjectName:
    Type: String
  Environment:
    Type: String
  AlertEmail:
    Type: String
  MlFunctionArn:
    Type: String
  TriageFunctionArn:
    Type: String
  RemediationFunctionArn:
    Type: String
  StateTableName:
    Type: String

Resources:
  AlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub "${ProjectName}-${Environment}-alerts"

  AlertSubscription:
    Type: AWS::SNS::Subscription
    Properties:
      Endpoint: !Ref AlertEmail
      Protocol: email
      TopicArn: !Ref AlertTopic

  WorkflowRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: states.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: InvokeLambda
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: lambda:InvokeFunction
                Resource:
                  - !Ref MlFunctionArn
                  - !Ref TriageFunctionArn
                  - !Ref RemediationFunctionArn
        - PolicyName: DynamoDBWrite
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: dynamodb:PutItem
                Resource: !Sub "arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${StateTableName}"
        - PolicyName: BedrockInvoke
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: bedrock:InvokeModel
                Resource: '*'
        - PolicyName: PublishAlerts
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: sns:Publish
                Resource: !Ref AlertTopic

  SocWorkflow:
    Type: AWS::StepFunctions::StateMachine
    Properties:
      StateMachineName: !Sub "${ProjectName}-${Environment}-soc"
      RoleArn: !GetAtt WorkflowRole.Arn
      DefinitionString: !Sub |
        {
          "Comment": "Autonomous SOC Workflow",
          "StartAt": "MLInference",
          "States": {
            "MLInference": {
              "Type": "Task",
              "Resource": "${MlFunctionArn}",
              "Next": "AlertTriage",
              "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "ErrorHandler"}]
            },
            "AlertTriage": {
              "Type": "Task",
              "Resource": "${TriageFunctionArn}",
              "Next": "CheckPriority"
            },
            "CheckPriority": {
              "Type": "Choice",
              "Choices": [{
                "Variable": "$.triage.priority_score",
                "NumericGreaterThan": 80,
                "Next": "BedrockAnalysis"
              }],
              "Default": "StoreAlert"
            },
            "BedrockAnalysis": {
              "Type": "Task",
              "Resource": "arn:aws:states:::bedrock:invokeModel",
              "Parameters": {
                "ModelId": "anthropic.claude-v2",
                "Body": {
                  "prompt": "Analyze this security alert and recommend action",
                  "max_tokens_to_sample": 500
                }
              },
              "Next": "DecideAction"
            },
            "DecideAction": {
              "Type": "Choice",
              "Choices": [{
                "Variable": "$.triage.auto_remediate",
                "BooleanEquals": true,
                "Next": "AutoRemediate"
              }],
              "Default": "NotifyHuman"
            },
            "AutoRemediate": {
              "Type": "Task",
              "Resource": "${RemediationFunctionArn}",
              "Next": "StoreAlert"
            },
            "NotifyHuman": {
              "Type": "Task",
              "Resource": "arn:aws:states:::sns:publish",
              "Parameters": {
                "TopicArn": "${AlertTopic}",
                "Message": "High-priority alert requires human review"
              },
              "Next": "StoreAlert"
            },
            "StoreAlert": {
              "Type": "Task",
              "Resource": "arn:aws:states:::dynamodb:putItem",
              "Parameters": {
                "TableName": "${StateTableName}",
                "Item": {
                  "alert_id": {"S": "$.event_id"},
                  "timestamp": {"S": "$.timestamp"},
                  "data": {"S": "States.JsonToString($)"}
                }
              },
              "End": true
            },
            "ErrorHandler": {
              "Type": "Pass",
              "Result": "Error occurred in workflow",
              "End": true
            }
          }
        }

Outputs:
  WorkflowArn:
    Value: !Ref SocWorkflow
  AlertTopicArn:
    Value: !Ref AlertTopic
```

---

## Cost Estimates

### Monthly Cost Breakdown (Development)

**Assumptions**: 
- 1,000 security events/day
- 30,000 events/month
- Development environment (not 24/7 production)

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| **Lambda** | 30K invocations × 3 functions | $3 |
| **Kinesis** | 1 shard | $15 |
| **OpenSearch Serverless** | 2 OCUs | $200 |
| **SageMaker Serverless** | 30K inferences | $30 |
| **Step Functions** | 30K executions | $1 |
| **S3** | 50 GB storage | $1 |
| **DynamoDB** | On-demand, 30K writes | $2 |
| **CloudWatch Logs** | 10 GB | $5 |
| **Data Transfer** | Minimal | $5 |
| **Total** | | **~$262/month** |

### Production Cost (10,000 events/day)

| Service | Monthly Cost |
|---------|--------------|
| Lambda | $10 |
| Kinesis | $45 (3 shards) |
| OpenSearch Serverless | $400 (4 OCUs) |
| SageMaker Serverless | $100 |
| Step Functions | $3 |
| S3 | $5 |
| DynamoDB | $7 |
| CloudWatch | $15 |
| **Total** | **~$585/month** |

**Cost Optimization Tips**:
- Use S3 for log archival (cheaper than OpenSearch)
- Enable CloudWatch Logs data compression
- Use Lambda Reserved Concurrency to control costs
- Right-size OpenSearch OCUs based on actual load

---

## Next Steps

### Phase 1 Checklist

- [ ] Set up AWS account and configure credentials
- [ ] Install support tooling (AWS CLI, SAM CLI, Python)
- [ ] Create versioned S3 artifact bucket + upload CloudFormation templates
- [ ] Configure GitHub Actions secrets/variables for `eu-central-1`
- [ ] Deploy event-ingestion nested stack via CI Change Set
- [ ] Test EventBridge → Lambda → Kinesis flow
- [ ] Deploy OpenSearch Serverless
- [ ] Verify events stored in OpenSearch
- [ ] Create basic dashboard in OpenSearch

### Phase 2 Checklist

- [ ] Train ML model (or use pre-trained from AI_SOC)
- [ ] Upload model to S3
- [ ] Update CloudFormation parameters to reference model artifact
- [ ] Deploy SageMaker Serverless endpoint + inference Lambda via CI
- [ ] Ensure alert triage Lambda artifact is published
- [ ] Create Step Functions workflow through orchestration stack update
- [ ] Test end-to-end flow with sample event
- [ ] Verify autonomous response

### Phase 3 Checklist

- [ ] Enable Amazon Bedrock in AWS account
- [ ] Create Bedrock knowledge base (MITRE ATT&CK)
- [ ] Configure Bedrock agent
- [ ] Integrate agent into Step Functions
- [ ] Test RAG-enhanced analysis
- [ ] Implement multi-step reasoning

### Phase 4 Checklist

- [ ] Security hardening (least privilege IAM)
- [ ] Enable encryption at rest/in transit
- [ ] Set up CloudWatch dashboards
- [ ] Configure alarms for critical metrics
- [ ] Document runbooks for incident response
- [ ] Cost optimization review
- [ ] Load testing
- [ ] Backup and disaster recovery plan

---

## Troubleshooting

### Common Issues

timeout = 60  # seconds
**Issue**: CloudFormation Change Set stuck in `REVIEW_IN_PROGRESS`
```bash
# Solution: Confirm the template was uploaded to the artifact bucket
aws cloudformation describe-change-set \
  --stack-name serverless-soc-dev \
  --change-set-name <name> \
  --region eu-central-1

# If obsolete, delete and re-run CI plan
aws cloudformation delete-change-set --stack-name serverless-soc-dev --change-set-name <name>
```

**Issue**: Stack rollback because Lambda artifact missing
```bash
# Solution: Ensure lambda-build workflow pushed the latest zip
aws s3 ls s3://soc-artifacts-dev/packages/ --region eu-central-1
# Re-run lambda-build.yml before re-deploying
```

**Issue**: Lambda function timeout
```bash
# Solution: Increase timeout/memory inside the relevant nested template and redeploy
```

**Issue**: SageMaker endpoint not responding
```bash
# Solution: Check endpoint status
aws sagemaker describe-endpoint --endpoint-name <name>
```

**Issue**: OpenSearch not accepting data
```bash
# Solution: Check network policy and IAM permissions in storage.yaml
# Verify Lambda role has opensearchserverless:BatchGetCollection permission
```

---

## Additional Resources

### Documentation
- AWS Lambda: https://docs.aws.amazon.com/lambda/
- Amazon OpenSearch Serverless: https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html
- Amazon SageMaker: https://docs.aws.amazon.com/sagemaker/
- Amazon Bedrock: https://docs.aws.amazon.com/bedrock/
- AWS CloudFormation: https://docs.aws.amazon.com/cloudformation/

### Original AI_SOC Project
- Repository: https://github.com/zhadyz/AI_SOC
- Documentation: See repository README
- Research Paper: "AI-Augmented SOC: A Survey of LLMs and Agents for Security Automation"

### Community
- AWS Security Hub: https://aws.amazon.com/security-hub/
- MITRE ATT&CK: https://attack.mitre.org/
- OWASP: https://owasp.org/

---

## Conclusion

You now have a complete guide to build a **serverless, scalable, autonomous SOC on AWS**. This architecture:

✅ **Costs 40-60% less** than container-based solutions
✅ **Scales automatically** from 0 to millions of events
✅ **Requires zero infrastructure management**
✅ **Implements agentic AI** for autonomous decision-making
✅ **Deploys via Infrastructure as Code** (CloudFormation + GitHub Actions)

**Next Action**: Start with Phase 1 to deploy the foundation infrastructure.

---

## Appendix: Quick Reference Commands

```bash
# Initialize project
mkdir aws-serverless-soc && cd aws-serverless-soc
git init
aws cloudformation validate-template \
  --template-body file://cloudformation/root-stack.yaml \
  --region eu-central-1

# Package and deploy (manual fallback)
aws cloudformation package \
  --template-file cloudformation/root-stack.yaml \
  --s3-bucket soc-artifacts-dev \
  --s3-prefix templates \
  --output-template-file packaged-root.yaml \
  --region eu-central-1

aws cloudformation deploy \
  --template-file packaged-root.yaml \
  --stack-name serverless-soc-dev \
  --parameter-overrides file://cloudformation/parameters/dev.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-central-1

# Check deployment
aws cloudformation describe-stacks --stack-name serverless-soc-dev --region eu-central-1 \
  --query "Stacks[0].Outputs"

# Monitor logs
aws logs tail /aws/lambda/serverless-soc-event-normalizer --follow

# Test event ingestion
aws events put-events --entries file://test-event.json

# Destroy infrastructure (cleanup)
aws cloudformation delete-stack --stack-name serverless-soc-dev --region eu-central-1
```

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Author**: AWS Serverless SOC Project  
**License**: MIT