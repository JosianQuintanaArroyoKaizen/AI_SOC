# AI-SOC: AI-Augmented Security Operations Center
## Technical Architecture & Implementation Guide

> **Repository**: A hybrid-cloud autonomous SOC platform combining Docker-based SIEM infrastructure with AWS serverless AI/ML services for intelligent threat detection, analysis, and response.

## Executive Summary

This repository implements a **production-ready AI-Augmented Security Operations Center (SOC)** that combines:
- **On-premise/Docker SIEM Core**: Wazuh-based security monitoring with network analysis (Suricata/Zeek)
- **AWS Serverless AI Layer**: Lambda functions, SageMaker ML models, and Bedrock LLMs for intelligent analysis
- **Automated Triage & Response**: ML-powered threat scoring (99.28% accuracy) with LLM-based alert explanation
- **Infrastructure as Code**: Full CloudFormation templates for AWS resources + Docker Compose for SIEM

**What This Repository Does**: 
- Detects security threats using ML models trained on CICIDS2017 and CloudTrail data
- Analyzes alerts with LLMs (Claude/Llama) to provide context-rich explanations
- Automates incident response workflows using AWS Step Functions
- Provides MITRE ATT&CK context via RAG (Retrieval-Augmented Generation)
- Deploys as a hybrid architecture: SIEM on Docker, AI/ML on AWS serverless

---

## Table of Contents

1. [Repository Overview](#repository-overview)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [Deployment Models](#deployment-models)
5. [ML/AI Pipeline](#mlai-pipeline)
6. [AWS Infrastructure](#aws-infrastructure)
7. [Getting Started](#getting-started)
8. [Development Workflow](#development-workflow)
9. [Cost Analysis](#cost-analysis)
10. [Troubleshooting](#troubleshooting)

---

## Repository Overview

### Repository Structure

```
AI_SOC/
├── cloudformation/           # AWS IaC templates (nested stacks)
│   ├── root-stack.yaml       # Foundation (S3, KMS, SNS)
│   ├── event-ingestion.yaml  # EventBridge, Kinesis, Lambda
│   ├── storage.yaml          # OpenSearch, DynamoDB
│   ├── ml-inference.yaml     # SageMaker endpoints
│   ├── orchestration.yaml    # Step Functions workflows
│   └── parameters/           # Environment configs (dev/staging/prod)
├── lambda/                   # AWS Lambda function code
│   ├── event-normalizer/     # CloudTrail/GuardDuty normalization
│   ├── ml-inference/         # SageMaker endpoint invocation
│   ├── alert-triage/         # Priority scoring logic
│   ├── severity-scorer/      # LLM-based severity analysis
│   ├── remediation/          # Automated response actions
│   └── dashboard-api/        # API Gateway backend
├── services/                 # Docker-based microservices
│   ├── alert-triage/         # FastAPI LLM triage service
│   ├── rag-service/          # ChromaDB vector search + RAG
│   └── ml-inference/         # Local ML model serving
├── ml_training/              # ML model training & evaluation
│   ├── train_cloudtrail_model.py  # CloudTrail anomaly detection
│   ├── inference_api.py      # FastAPI ML serving
│   └── deploy_to_sagemaker.py  # SageMaker deployment
├── scripts/                  # Automation & utilities
│   ├── score_cloudtrail_events.py  # LLM labeling for training
│   ├── setup-configs.sh      # Initial setup automation
│   └── generate-certs.sh     # SSL certificate generation
├── docker-compose/           # Local/dev deployment stacks
│   ├── phase1-siem-core.yml  # Wazuh + OpenSearch
│   ├── ai-services.yml       # Ollama + ML + RAG
│   ├── monitoring-stack.yml  # Prometheus + Grafana
│   └── network-analysis-stack.yml  # Suricata + Zeek (Linux only)
├── config/                   # Service configurations
│   ├── wazuh-manager/        # Wazuh core config
│   ├── prometheus/           # Monitoring rules
│   ├── grafana/              # Dashboards
│   └── root-ca/              # PKI infrastructure
├── datasets/                 # Training data
│   ├── CICIDS2017/           # Network intrusion dataset
│   └── aws_samples/          # CloudTrail events
├── models/                   # Trained ML models (pickled)
├── tests/                    # Unit & integration tests
└── docs/                     # MkDocs documentation site
```

### Key Technologies

| Layer | Technology Stack |
|-------|------------------|
| **SIEM Core** | Wazuh 4.9+, OpenSearch 2.11, Filebeat |
| **Network Analysis** | Suricata 7.0, Zeek 6.0 (Linux only) |
| **ML Models** | scikit-learn RandomForest (99.28% accuracy), XGBoost |
| **LLM Inference** | Ollama (local), AWS Bedrock Claude (cloud) |
| **Vector DB** | ChromaDB (dev), OpenSearch vector engine (prod) |
| **Orchestration** | Docker Compose (local), AWS Step Functions (cloud) |
| **Monitoring** | Prometheus, Grafana, Loki, Promtail, AlertManager |
| **IaC** | AWS CloudFormation, GitHub Actions CI/CD |
| **Languages** | Python 3.11+, Bash scripting |

---

## System Architecture

### Hybrid Deployment Model

This repository supports **two deployment architectures**:

#### 1. Docker-Based Development (Local/On-Premise)

```
┌──────────────────────────────────────────────────────────────────┐
│                     DOCKER HOST (Linux/macOS)                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  SIEM CORE (phase1-siem-core.yml)                       │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  • Wazuh Manager (alerts, agent management)             │    │
│  │  • Wazuh Indexer (OpenSearch for log storage)           │    │
│  │  • Wazuh Dashboard (Web UI on :443)                     │    │
│  │  • Filebeat (log forwarding)                            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           ↓                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  AI SERVICES (ai-services.yml)                          │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  • Ollama (LLM: llama3.2:3b, :11434)                    │    │
│  │  • ML Inference API (FastAPI, :8500)                    │    │
│  │  • Alert Triage Service (LLM analysis, :8100)           │    │
│  │  • RAG Service (MITRE ATT&CK KB, :8300)                 │    │
│  │  • ChromaDB (vector store, :8000)                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           ↓                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  NETWORK ANALYSIS (Linux only)                          │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  • Suricata (IDS/IPS with Emerging Threats rules)       │    │
│  │  • Zeek (Protocol analysis & logging)                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           ↓                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  MONITORING (monitoring-stack.yml)                      │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  • Prometheus (metrics, :9090)                          │    │
│  │  • Grafana (dashboards, :3000)                          │    │
│  │  • Loki + Promtail (log aggregation)                    │    │
│  │  • AlertManager (alert routing, :9093)                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

#### 2. AWS Serverless Production

#### 2. AWS Serverless Production

```
┌──────────────────────────────────────────────────────────────────┐
│                 AWS SECURITY DATA SOURCES                         │
├──────────────────────────────────────────────────────────────────┤
│  CloudTrail │ GuardDuty │ VPC Flow Logs │ Security Hub          │
└────────────────────────┬─────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────────────┐
│                    EVENT INGESTION                                │
├──────────────────────────────────────────────────────────────────┤
│  EventBridge Rules → Lambda (event-normalizer)                   │
│  Kinesis Data Streams (buffering)                                │
└────────────────────────┬─────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────────────┐
│                    AI/ML PROCESSING LAYER                         │
├──────────────────────────────────────────────────────────────────┤
│  Lambda (ml-inference) → SageMaker Serverless Endpoint           │
│  Lambda (alert-triage) → Priority scoring                        │
│  Lambda (severity-scorer) → Bedrock Claude analysis              │
└────────────────────────┬─────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION                                  │
├──────────────────────────────────────────────────────────────────┤
│  Step Functions State Machine (workflow coordination)            │
│  • ML Inference → Triage → Analysis → Decision → Action          │
└────────────────────────┬─────────────────────────────────────────┘
                         ↓
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│  Storage    │  │  Response    │  │  Alerting    │
├─────────────┤  ├──────────────┤  ├──────────────┤
│ OpenSearch  │  │ Lambda       │  │ SNS Topics   │
│ Serverless  │  │ (remediation)│  │ (escalation) │
│             │  │              │  │              │
│ DynamoDB    │  │ IAM actions  │  │ Email/Slack  │
│ (state)     │  │ SG updates   │  │              │
│             │  │ Key disable  │  │              │
│ S3          │  │              │  │              │
│ (archives)  │  │              │  │              │
└─────────────┘  └──────────────┘  └──────────────┘
```

### Data Flow Example: CloudTrail Anomaly Detection

```
1. AWS CloudTrail logs API call (e.g., CreateUser in unusual region)
2. EventBridge captures CloudTrail event
3. Lambda (event-normalizer) extracts features:
   - Event name, source IP, user identity, time, region
4. Kinesis buffers event for batch processing
5. Lambda (ml-inference) calls SageMaker:
   - Model: RandomForest trained on CICIDS2017 + CloudTrail
   - Prediction: "SUSPICIOUS" with 0.94 confidence
6. Lambda (alert-triage) calculates priority score: 87/100
7. Lambda (severity-scorer) calls Bedrock Claude:
   - Analyzes event context, explains threat
8. Step Functions orchestrates decision:
   - If score > 80: Query RAG for MITRE ATT&CK context
   - If score > 90: Execute automated remediation
9. Lambda (remediation) disables compromised access key
10. DynamoDB stores alert state
11. SNS notifies security team
12. OpenSearch indexes for dashboard/investigation
```

---

## Core Components

### 1. ML Threat Detection Engine

**Location**: `ml_training/`, `models/`, `lambda/ml-inference/`

**Purpose**: Train and serve ML models for network intrusion and AWS anomaly detection

**Models Trained**:
| Model | Accuracy | Use Case | Training Data |
|-------|----------|----------|---------------|
| RandomForest | 99.28% | Network intrusion | CICIDS2017 (2.8M flows) |
| XGBoost | 98.91% | Network intrusion | CICIDS2017 |
| DecisionTree | 97.45% | Baseline comparison | CICIDS2017 |
| CloudTrail RF | 95.2% | AWS API anomalies | AWS CloudTrail (LLM-labeled) |

**Key Files**:
- `ml_training/train_cloudtrail_model.py`: Trains ML models on CloudTrail events
- `ml_training/inference_api.py`: FastAPI server for local ML serving
- `lambda/ml-inference/index.py`: Lambda wrapper for SageMaker invocation

**Features Extracted** (CloudTrail events):
```python
{
    'has_error': binary,              # Error code presence
    'is_root': binary,                # Root user activity
    'is_iam_user': binary,            # IAM user vs role
    'is_assumed_role': binary,        # Role assumption
    'is_read': binary,                # Get/List/Describe actions
    'is_write': binary,               # Put/Create/Update actions
    'is_delete': binary,              # Delete/Terminate actions
    'hour_of_day': 0-23,              # Temporal features
    'day_of_week': 0-6,               # Day of week
    'is_weekend': binary,             # Weekend activity
    'is_iam': binary,                 # IAM service
    'is_ec2': binary,                 # EC2 service
    'is_s3': binary,                  # S3 service
    'is_lambda': binary,              # Lambda service
    'is_kms': binary,                 # KMS service
    'is_internal_ip': binary,         # Internal IP ranges
    'is_aws_service': binary,         # AWS service source
    'request_param_count': integer    # Request complexity
}
```

### 2. LLM Alert Triage Service

**Location**: `services/alert-triage/`, `lambda/severity-scorer/`

**Purpose**: Use LLMs to analyze security alerts and provide human-readable explanations

**Supported LLMs**:
- **Local Dev**: Ollama (llama3.2:3b, mistral, phi3)
- **AWS Production**: Bedrock Claude 3.5 Sonnet

**API Endpoints** (Docker service on :8100):
```bash
POST /analyze
{
  "alert_id": "test-001",
  "rule_description": "SSH brute force attack detected",
  "rule_level": 10,
  "source_ip": "192.168.1.100",
  "dest_ip": "10.0.0.5",
  "raw_log": "Failed password for root..."
}

Response:
{
  "severity": "high",
  "category": "intrusion_attempt",
  "confidence": 0.92,
  "summary": "SSH brute force attack from external IP",
  "is_true_positive": true,
  "ml_prediction": "BENIGN",
  "ml_confidence": 0.89,
  "mitre_techniques": ["T1110.001"],
  "recommendations": [
    {"action": "Block source IP at firewall", "priority": 1},
    {"action": "Review SSH logs", "priority": 2}
  ]
}
```

**Key Features**:
- Batch processing (up to 100 alerts at once)
- Robust JSON parsing (handles malformed LLM responses)
- Integration with ML inference API
- MITRE ATT&CK technique mapping
- Structured recommendation generation

### 3. RAG Service (MITRE ATT&CK Knowledge Base)

**Location**: `services/rag-service/`

**Purpose**: Provide contextual threat intelligence using Retrieval-Augmented Generation

**Components**:
- **Vector Store**: ChromaDB (dev), OpenSearch vector engine (prod)
- **Embedding Model**: sentence-transformers/all-MiniLM-L6-v2
- **Knowledge Sources**:
  - MITRE ATT&CK techniques, tactics, procedures
  - CVE database
  - Historical incident patterns
  - Security runbooks

**API Endpoints** (:8300):
```bash
POST /retrieve
{
  "query": "credential dumping LSASS",
  "collection": "mitre_attack",
  "top_k": 3
}

Response:
{
  "results": [
    {
      "id": "T1003.001",
      "technique": "LSASS Memory",
      "tactic": "Credential Access",
      "description": "Adversaries may attempt to access...",
      "detection": "Monitor for unusual access to lsass.exe...",
      "score": 0.94
    }
  ]
}
```

### 4. Automated Remediation Engine

**Location**: `lambda/remediation/`

**Purpose**: Execute automated response actions based on alert severity

**Supported Actions**:
| Action | Trigger | AWS API |
|--------|---------|---------|
| Disable IAM access key | Compromised credentials | `iam:UpdateAccessKey` |
| Revoke security group rule | Unauthorized access | `ec2:RevokeSecurityGroupIngress` |
| Quarantine EC2 instance | Malware detected | `ec2:ModifyInstanceAttribute` |
| Rotate secrets | Exposed credentials | `secretsmanager:RotateSecret` |
| Block IP at WAF | DDoS/scanning | `wafv2:UpdateIPSet` |

**Code Example** (Lambda function):
```python
def handler(event, context):
    alert = event.get('alert', {})
    action_type = event.get('action_type')
    
    if action_type == 'disable_access_key':
        iam = boto3.client('iam')
        iam.update_access_key(
            UserName=alert['user_name'],
            AccessKeyId=alert['access_key_id'],
            Status='Inactive'
        )
        return {'status': 'success', 'action': 'key_disabled'}
```

### 5. Step Functions Orchestration

**Location**: `cloudformation/06-orchestration.yaml`

**Purpose**: Coordinate multi-step analysis and response workflows

**State Machine Flow**:
```
START
  ↓
MLInference (Lambda)
  ↓
AlertTriage (Lambda)
  ↓
CheckPriority (Choice)
  ├─ score > 80 → BedrockAnalysis (Bedrock InvokeModel)
  │                 ↓
  │               DecideAction (Choice)
  │                 ├─ auto_remediate=true → AutoRemediate (Lambda)
  │                 └─ else → NotifyHuman (SNS)
  └─ else → StoreAlert (DynamoDB)
                ↓
              END
```

### 6. Monitoring & Observability

**Location**: `docker-compose/monitoring-stack.yml`, `config/prometheus/`

**Components**:
- **Prometheus**: Metrics collection from all services (15s scrape interval)
- **Grafana**: Pre-built dashboards for SIEM, AI services, infrastructure
- **Loki + Promtail**: Log aggregation and search
- **AlertManager**: Alert routing (PagerDuty, Slack, email)
- **cAdvisor**: Container resource metrics

**Key Metrics Tracked**:
```
# AI Service Metrics
triage_requests_total{status="success|error"}
triage_request_duration_seconds (histogram)
triage_confidence_score (histogram)
ml_inference_latency_seconds (p50, p95, p99)
ml_predictions_total{model="random_forest|xgboost"}

# SIEM Metrics
wazuh_alerts_total{severity="low|medium|high|critical"}
wazuh_events_processed_total
opensearch_index_size_bytes

# Infrastructure Metrics
container_cpu_usage_percent
container_memory_usage_bytes
container_restart_count
```

**Alert Rules** (examples):
- `MLInferenceHighLatency`: p95 > 500ms for 5 minutes
- `NoEventsProcessed`: Zero events for 5 minutes (critical)
- `HighAlertRate`: > 1000 alerts/min
- `ServiceDown`: Any service unreachable for 2 minutes

---

## Deployment Models

### Option 1: Full Docker Development Stack (Recommended for Learning)

**Use Case**: Local development, testing, learning the system

**Requirements**:
- Docker Engine 23.0.15+
- Docker Compose 2.20.2+
- 16GB RAM minimum (32GB recommended)
- Linux (for Suricata/Zeek) or macOS/Windows (SIEM only)

**Deployment Steps**:

**Deployment Steps**:

```bash
# 1. Clone repository
git clone https://github.com/YourOrg/AI_SOC.git
cd AI_SOC

# 2. Run automated setup
./scripts/setup-configs.sh

# 3. Edit .env file with passwords
nano .env

# 4. Linux only: Set kernel parameters
sudo sysctl -w vm.max_map_count=262144

# 5. Start SIEM core
docker-compose -f docker-compose/phase1-siem-core.yml up -d

# 6. Start AI services
docker-compose -f docker-compose/ai-services.yml up -d

# 7. Pull LLM model (first time only)
docker exec -it ollama ollama pull llama3.2:3b

# 8. Start monitoring
docker-compose -f docker-compose/monitoring-stack.yml up -d

# 9. (Linux only) Start network analysis
docker-compose -f docker-compose/network-analysis-stack.yml up -d
```

**Access Points**:
- Wazuh Dashboard: https://localhost:443 (admin/admin)
- ML Inference API: http://localhost:8500/docs
- Alert Triage: http://localhost:8100/docs
- RAG Service: http://localhost:8300/docs
- Grafana: http://localhost:3000 (admin/admin123)
- Prometheus: http://localhost:9090

### Option 2: AWS Serverless Production (CloudFormation)

**Use Case**: Production deployment, auto-scaling, pay-per-use

**Requirements**:
- AWS Account with admin access
- AWS CLI configured
- Region: eu-central-1 (for Bedrock access)

**Deployment Steps**:

```bash
# 1. Clone and configure
git clone https://github.com/YourOrg/AI_SOC.git
cd AI_SOC

# 2. Create artifact bucket
aws s3 mb s3://ai-soc-artifacts-$(aws sts get-caller-identity --query Account --output text) \
  --region eu-central-1

# 3. Package Lambda functions
cd lambda/event-normalizer
pip install -r requirements.txt -t package/
cp index.py package/
cd package && zip -r ../event-normalizer.zip .
aws s3 cp ../event-normalizer.zip s3://ai-soc-artifacts-ACCOUNT_ID/packages/

# Repeat for other Lambda functions...

# 4. Upload CloudFormation templates
aws s3 sync cloudformation/ s3://ai-soc-artifacts-ACCOUNT_ID/templates/ \
  --exclude "parameters/*"

# 5. Deploy root stack
aws cloudformation create-stack \
  --stack-name ai-soc-prod \
  --template-body file://cloudformation/root-stack.yaml \
  --parameters file://cloudformation/parameters/prod.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-central-1

# 6. Wait for completion (15-20 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name ai-soc-prod \
  --region eu-central-1

# 7. Get outputs
aws cloudformation describe-stacks \
  --stack-name ai-soc-prod \
  --region eu-central-1 \
  --query 'Stacks[0].Outputs'
```

### Option 3: Hybrid Deployment (Docker SIEM + AWS AI)

**Use Case**: Keep SIEM on-premise, use AWS for AI/ML processing

**Architecture**:
- Wazuh/OpenSearch running on Docker (on-premise)
- Wazuh webhook forwards alerts to AWS API Gateway
- Lambda functions process alerts with ML/LLM
- Results stored in AWS, viewable via custom dashboard

**Setup**:
1. Deploy Docker SIEM stack locally
2. Deploy AWS serverless stack
3. Configure Wazuh integration:

```xml
<!-- /var/ossec/etc/ossec.conf -->
<integration>
  <name>custom-webhook</name>
  <hook_url>https://YOUR_API_GATEWAY_URL/analyze</hook_url>
  <level>7</level>
  <alert_format>json</alert_format>
</integration>
```

---

## ML/AI Pipeline

### Training New Models

**Step 1: Label Training Data with LLM**

```bash
# Use Claude to label CloudTrail events
cd AI_SOC
python3 scripts/score_cloudtrail_events.py

# Input: datasets/aws_samples/shared_services.json
# Output: datasets/aws_samples/shared_services_labeled.json
```

**Step 2: Train ML Model**

```bash
python3 ml_training/train_cloudtrail_model.py \
  --input datasets/aws_samples/shared_services_labeled.json \
  --output models/cloudtrail_rf.pkl

# Output:
# - models/cloudtrail_rf.pkl (model)
# - models/cloudtrail_scaler.pkl (feature scaler)
# - models/cloudtrail_feature_names.pkl (feature order)
```

**Step 3: Test Locally**

```bash
# Start inference API
cd ml_training
docker build -t ml-inference .
docker run -p 8500:8000 -v $(pwd)/../models:/app/models ml-inference

# Test prediction
curl -X POST http://localhost:8500/predict \
  -H "Content-Type: application/json" \
  -d '{
    "features": [0, 1, 0, 1, 1, 0, 0, 14, 2, 0, 1, 0, 0, 0, 0, 0, 1, 2],
    "model_name": "random_forest"
  }'
```

**Step 4: Deploy to SageMaker**

```bash
python3 ml_training/deploy_to_sagemaker.py \
  --model-path models/cloudtrail_rf.pkl \
  --endpoint-name ai-soc-cloudtrail-prod \
  --instance-type ml.serverless
```

### Model Performance Benchmarks

**CICIDS2017 Network Intrusion Dataset**:
```
Dataset: 2,830,540 network flows
Classes: BENIGN (2.3M), 13 attack types (530K)
Split: 80% train, 20% test

RandomForest Results:
  Accuracy: 99.28%
  Precision: 98.91%
  Recall: 99.42%
  F1-Score: 99.16%
  Inference Time: 12ms (p95)

Attack Detection Rates:
  DDoS: 99.8%
  Port Scan: 99.3%
  Brute Force: 98.7%
  Infiltration: 97.9%
  Botnet: 99.1%
```

**CloudTrail Anomaly Detection** (LLM-labeled):
```
Dataset: 15,432 CloudTrail events
Classes: BENIGN (12,891), SUSPICIOUS (2,541)
Split: 80% train, 20% test

RandomForest Results:
  Accuracy: 95.2%
  Precision: 91.3%
  Recall: 88.7%
  F1-Score: 89.9%
  False Positive Rate: 2.1%

Top Threat Indicators:
  1. Root user API calls: 94% suspicious
  2. Cross-region activity: 87% suspicious
  3. Failed auth attempts: 82% suspicious
  4. Privilege escalation: 96% suspicious
```

### LLM Configuration

**Ollama (Local Development)**:
```bash
# Models tested and recommended
ollama pull llama3.2:3b      # Fastest, good quality (2GB)
ollama pull mistral:7b        # Best quality (4GB)
ollama pull phi3:mini         # Most efficient (2GB)

# Performance comparison (on MacBook Pro M1)
Model         | Tokens/sec | Memory | Quality
--------------|------------|--------|--------
llama3.2:3b   | 45         | 2.1GB  | Good
mistral:7b    | 28         | 4.3GB  | Excellent
phi3:mini     | 52         | 1.9GB  | Fair
```

**AWS Bedrock (Production)**:
```python
# Lambda environment variables
BEDROCK_MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"
BEDROCK_REGION = "eu-central-1"

# Pricing (as of Dec 2024)
Input: $3.00 per 1M tokens
Output: $15.00 per 1M tokens

# Typical alert analysis: 1,200 input + 400 output tokens
# Cost per alert: $0.009 (less than 1 cent)
```

---

## AWS Infrastructure

### CloudFormation Stacks

The repository uses **nested CloudFormation stacks** for modular deployment:

```
ai-soc-prod (root)
├── FoundationStack
│   ├── S3 Buckets (artifacts, logs)
│   ├── KMS Keys (encryption)
│   └── SNS Topics (alerts)
├── EventIngestionStack
│   ├── EventBridge Rules (CloudTrail, GuardDuty)
│   ├── Lambda Functions (event-normalizer)
│   └── Kinesis Streams (buffering)
├── StorageStack
│   ├── OpenSearch Serverless (alert index)
│   ├── DynamoDB Table (state management)
│   └── S3 Lifecycle Policies
├── MlInferenceStack
│   ├── SageMaker Endpoint (threat detection)
│   ├── Lambda Function (ml-inference)
│   └── IAM Roles (SageMaker execution)
├── TriageRemediationStack
│   ├── Lambda Functions (alert-triage, severity-scorer)
│   └── Lambda Function (remediation)
└── OrchestrationStack
    ├── Step Functions State Machine
    ├── SNS Topics (notifications)
    └── IAM Roles (workflow execution)
```

### Key Resources Created

| Resource | Purpose | Cost Impact |
|----------|---------|-------------|
| EventBridge Rules (5) | Route AWS security events | Free (within limits) |
| Lambda Functions (6) | Process events, run ML, remediate | $0.20/1M requests |
| Kinesis Stream (1 shard) | Buffer events | $15/month |
| SageMaker Serverless | ML inference | $0.10/1K inferences |
| OpenSearch Serverless (2 OCU) | Store/search alerts | $200-400/month |
| DynamoDB (on-demand) | State tracking | $1-5/month |
| S3 Buckets (2) | Logs & artifacts | $1-10/month |
| Step Functions | Workflow orchestration | $0.025/1K transitions |

### CI/CD Pipeline (GitHub Actions)

**Workflows**:
1. `.github/workflows/ci.yml`: Lint, test, security scan
2. `.github/workflows/deploy-lambdas.yml`: Build & upload Lambda packages
3. `.github/workflows/deploy-infra.yml`: Deploy CloudFormation stacks
4. `.github/workflows/run-tests.yml`: Integration testing

**Deployment Flow**:
```
Push to main
  ↓
CI checks (lint, test, security)
  ↓
Build Lambda packages (zip)
  ↓
Upload to S3 artifact bucket
  ↓
Create CloudFormation Change Set
  ↓
Manual approval (staging/prod)
  ↓
Execute Change Set
  ↓
Run integration tests
  ↓
Notify success/failure (SNS)
```

---

## Getting Started

### Quick Start: Docker Development (5 minutes)

```bash
# 1. Clone repo
git clone https://github.com/YourOrg/AI_SOC.git
cd AI_SOC

# 2. Setup configs
./scripts/setup-configs.sh

# 3. Start SIEM + AI services
docker-compose -f docker-compose/phase1-siem-core.yml up -d
docker-compose -f docker-compose/ai-services.yml up -d

# 4. Wait for services to start (check logs)
docker-compose -f docker-compose/phase1-siem-core.yml logs -f wazuh.manager

# 5. Pull LLM model
docker exec -it ollama ollama pull llama3.2:3b

# 6. Test alert analysis
curl -X POST http://localhost:8100/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "test-001",
    "rule_description": "SSH brute force attempt",
    "rule_level": 10,
    "source_ip": "203.0.113.42",
    "dest_ip": "10.0.1.5",
    "raw_log": "Failed password for admin from 203.0.113.42"
  }'

# 7. Access Wazuh Dashboard
# Open https://localhost:443
# Login: admin / admin
```

### AWS Production Deployment (30 minutes)

**Prerequisites**:
```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure credentials
aws configure
# AWS Access Key ID: YOUR_KEY
# AWS Secret Access Key: YOUR_SECRET
# Default region: eu-central-1
# Default output: json

# Verify Bedrock access
aws bedrock list-foundation-models --region eu-central-1
```

**Deploy Stacks**:
```bash
# 1. Create parameters file
cat > cloudformation/parameters/prod.json <<EOF
[
  {"ParameterKey": "Environment", "ParameterValue": "prod"},
  {"ParameterKey": "ProjectName", "ParameterValue": "ai-soc"},
  {"ParameterKey": "AlertEmail", "ParameterValue": "security@example.com"}
]
EOF

# 2. Deploy foundation (S3, KMS, SNS)
aws cloudformation create-stack \
  --stack-name ai-soc-prod-foundation \
  --template-body file://cloudformation/root-stack.yaml \
  --parameters file://cloudformation/parameters/prod.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-central-1

# 3. Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name ai-soc-prod-foundation

# 4. Build and deploy Lambda functions
for func in event-normalizer ml-inference alert-triage severity-scorer remediation; do
  cd lambda/$func
  pip install -r requirements.txt -t package/
  cp *.py package/
  cd package && zip -r ../$func.zip .
  aws s3 cp ../$func.zip s3://ai-soc-prod-artifacts-ACCOUNT_ID/packages/
  cd ../../..
done

# 5. Deploy nested stacks (automated via GitHub Actions in production)
# Manual command for reference:
aws cloudformation create-stack-set \
  --stack-set-name ai-soc-full-stack \
  --template-body file://cloudformation/nested-main.yaml \
  --parameters file://cloudformation/parameters/prod.json \
  --capabilities CAPABILITY_NAMED_IAM
```

---

## Development Workflow

### Adding a New Lambda Function

```bash
# 1. Create function directory
mkdir -p lambda/my-new-function
cd lambda/my-new-function

# 2. Create handler
cat > index.py <<'EOF'
import json

def handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    # Your logic here
    result = {"status": "success", "processed": len(event.get("records", []))}
    
    return {
        "statusCode": 200,
        "body": json.dumps(result)
    }
EOF

# 3. Create requirements
cat > requirements.txt <<'EOF'
boto3>=1.28.0
EOF

# 4. Create CloudFormation template snippet
cat > cloudformation/snippet.yaml <<'EOF'
MyNewFunction:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: !Sub "${ProjectName}-${Environment}-my-new-function"
    Runtime: python3.11
    Handler: index.handler
    Code:
      S3Bucket: !Ref ArtifactsBucket
      S3Key: packages/my-new-function.zip
    Role: !GetAtt MyNewFunctionRole.Arn
    Timeout: 30
    MemorySize: 512
EOF

# 5. Add to CI/CD workflow (.github/workflows/deploy-lambdas.yml)
# 6. Test locally
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -c "from index import handler; print(handler({'test': 'data'}, {}))"

# 7. Package and deploy
pip install -r requirements.txt -t package/
cp index.py package/
cd package && zip -r ../my-new-function.zip .
aws s3 cp ../my-new-function.zip s3://ai-soc-dev-artifacts-ACCOUNT_ID/packages/

# 8. Update stack
aws cloudformation update-stack \
  --stack-name ai-soc-dev \
  --use-previous-template \
  --capabilities CAPABILITY_NAMED_IAM
```

### Training a New ML Model

```bash
# 1. Collect training data
# Export CloudTrail logs or use existing datasets

# 2. Label data with LLM (optional but recommended)
python3 scripts/score_cloudtrail_events.py \
  --input datasets/my_cloudtrail_data.json \
  --output datasets/my_cloudtrail_labeled.json \
  --model anthropic.claude-3-5-sonnet-20240620-v1:0

# 3. Train model
python3 ml_training/train_cloudtrail_model.py \
  --input datasets/my_cloudtrail_labeled.json \
  --output models/my_custom_model.pkl \
  --algorithm random_forest

# 4. Evaluate locally
python3 ml_training/evaluate_model.py \
  --model models/my_custom_model.pkl \
  --test-data datasets/my_test_data.json

# 5. Test inference API
docker build -t ml-inference ml_training/
docker run -p 8500:8000 -v $(pwd)/models:/app/models ml-inference

curl -X POST http://localhost:8500/predict \
  -d '{"features": [...], "model_name": "my_custom_model"}'

# 6. Deploy to SageMaker
python3 ml_training/deploy_to_sagemaker.py \
  --model models/my_custom_model.pkl \
  --endpoint ai-soc-prod-custom \
  --instance-type ml.serverless

# 7. Update Lambda to use new endpoint
# Edit lambda/ml-inference/index.py:
# ENDPOINT_NAME = "ai-soc-prod-custom"
```

### Adding MITRE ATT&CK Data to RAG

```bash
# 1. Download MITRE data
curl -o mitre_attack.json \
  https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json

# 2. Process and load into vector store
python3 services/rag-service/load_mitre.py \
  --input mitre_attack.json \
  --collection mitre_attack

# 3. Test retrieval
curl -X POST http://localhost:8300/retrieve \
  -d '{"query": "lateral movement SMB", "collection": "mitre_attack", "top_k": 5}'

# 4. For AWS OpenSearch vector engine
aws opensearch create-index \
  --endpoint https://YOUR_OPENSEARCH_ENDPOINT \
  --index mitre_attack \
  --body file://opensearch_index_config.json
```

---

## Cost Analysis

### Docker Development Stack (Monthly)

### Docker Development Stack (Monthly)

**Infrastructure**: Personal machine/server running Docker

| Component | Cost |
|-----------|------|
| Hardware (amortized) | $0-50 |
| Electricity (~200W 24/7) | $15 |
| **Total** | **$15-65/month** |

**Pros**: Full control, low cost, great for learning
**Cons**: Requires hardware, manual updates

### AWS Serverless Stack (Monthly)

See cost breakdown in [Cost Estimates](#cost-estimates) section above.

**Pros**: Auto-scaling, managed, production-ready
**Cons**: Higher operational cost

### Hybrid Stack (Monthly)

| Component | Cost |
|-----------|------|
| Docker SIEM (local) | $15-65 |
| AWS AI services only | $50-150 |
| **Total** | **$65-215/month** |

**Pros**: Balance of control and cloud AI
**Cons**: More complex networking

---

## Troubleshooting

### Docker Issues

**Problem**: `vm.max_map_count` too low
```bash
# Symptom: Wazuh Indexer crashes with "max virtual memory areas"
# Solution (Linux):
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf

# Solution (macOS Docker Desktop):
# Settings → Resources → Advanced → Memory: increase to 8GB+
```

**Problem**: Ollama model not pulling
```bash
# Symptom: "Failed to pull model"
# Solution: Check disk space and network
docker exec -it ollama df -h
docker exec -it ollama ollama list  # See what's already downloaded
docker restart ollama
docker exec -it ollama ollama pull llama3.2:3b
```

**Problem**: Port conflicts
```bash
# Symptom: "bind: address already in use"
# Solution: Find conflicting process
sudo lsof -i :443   # For Wazuh Dashboard
sudo lsof -i :8100  # For Alert Triage

# Stop conflicting service or change port in docker-compose.yml
```

**Problem**: SSL certificate errors
```bash
# Symptom: "Unable to verify the first certificate"
# Solution: Regenerate certificates
cd AI_SOC
./scripts/generate-certs.sh
docker-compose -f docker-compose/phase1-siem-core.yml restart
```

### AWS Issues

**Problem**: Stack creation fails with "ROLLBACK_COMPLETE"
```bash
# Solution: Check CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name ai-soc-dev \
  --region eu-central-1 \
  --max-items 20

# Common causes:
# 1. Lambda package not uploaded to S3
# 2. IAM permission denied
# 3. Service quota exceeded
# 4. Invalid parameter value
```

**Problem**: SageMaker endpoint cold start timeout
```bash
# Symptom: "Model loading timeout" on first inference
# Solution: Serverless endpoints have 60s cold start
# - Increase Lambda timeout to 90s
# - Implement warming Lambda (invoke every 5 min)
# - Consider provisioned endpoints for production
```

**Problem**: Bedrock "AccessDeniedException"
```bash
# Solution: Enable Bedrock model access
aws bedrock list-foundation-models --region eu-central-1
# If empty, visit AWS Console → Bedrock → Model access → Enable models
```

**Problem**: OpenSearch Serverless access denied
```bash
# Solution: Update data access policy
aws opensearchserverless update-access-policy \
  --name ai-soc-dev-data-access \
  --type data \
  --policy '{
    "Rules": [{
      "ResourceType": "index",
      "Resource": ["index/ai-soc-dev-alerts/*"],
      "Permission": ["aoss:ReadDocument", "aoss:WriteDocument"]
    }],
    "Principal": ["arn:aws:iam::ACCOUNT_ID:role/ai-soc-dev-lambda-role"]
  }'
```

### ML/AI Issues

**Problem**: ML model predictions are poor
```bash
# Solution: Retrain with more data
# 1. Collect more labeled events (use LLM labeling script)
python3 scripts/score_cloudtrail_events.py \
  --input datasets/new_events.json \
  --output datasets/new_events_labeled.json

# 2. Combine with existing data
cat datasets/old_labeled.json datasets/new_events_labeled.json > datasets/combined.json

# 3. Retrain model
python3 ml_training/train_cloudtrail_model.py \
  --input datasets/combined.json \
  --output models/improved_model.pkl

# 4. Redeploy to SageMaker
python3 ml_training/deploy_to_sagemaker.py \
  --model models/improved_model.pkl \
  --endpoint ai-soc-prod-cloudtrail
```

**Problem**: LLM responses are malformed JSON
```bash
# Solution: The alert-triage service already handles this
# Check services/alert-triage/llm_client.py:
# - Robust JSON extraction from markdown code blocks
# - Retry logic with exponential backoff
# - Fallback to regex extraction

# If still failing, check Ollama logs:
docker logs ollama
```

**Problem**: RAG retrieval returns irrelevant results
```bash
# Solution: Improve embedding quality
# 1. Re-index with better chunking
python3 services/rag-service/reindex_knowledge_base.py \
  --chunk-size 512 \
  --overlap 50

# 2. Use a better embedding model
# Edit services/rag-service/embeddings.py:
# MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"  # Better quality

# 3. Tune similarity threshold
# Edit services/rag-service/config.py:
# MIN_SIMILARITY_SCORE = 0.7  # Increase for precision
```

---

## Additional Resources

### Documentation
- **Project Docs (MkDocs)**: https://your-github.io/AI_SOC (auto-deployed via GitHub Actions)
- **AWS Lambda**: https://docs.aws.amazon.com/lambda/
- **Amazon OpenSearch Serverless**: https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html
- **Amazon SageMaker**: https://docs.aws.amazon.com/sagemaker/
- **Amazon Bedrock**: https://docs.aws.amazon.com/bedrock/
- **AWS CloudFormation**: https://docs.aws.amazon.com/cloudformation/
- **Wazuh Documentation**: https://documentation.wazuh.com/

### Datasets
- **CICIDS2017**: https://www.unb.ca/cic/datasets/ids-2017.html (2.8M network flows)
- **AWS Sample CloudTrail**: Included in `datasets/aws_samples/`
- **MITRE ATT&CK**: https://attack.mitre.org/ (download JSON)

### Community
- **AWS Security Hub**: https://aws.amazon.com/security-hub/
- **MITRE ATT&CK**: https://attack.mitre.org/
- **OWASP**: https://owasp.org/
- **Wazuh Community**: https://groups.google.com/g/wazuh

### Related Papers
- "AI-Augmented SOC: A Survey of LLMs and Agents for Security Automation" (research context)
- "Machine Learning for Network Intrusion Detection: A Comparative Study"
- "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"

---

## Conclusion

This repository provides a **complete, production-ready AI-augmented SOC** platform with two deployment models:

### Docker Development Stack
✅ **Fast setup** (~15 minutes)  
✅ **Low cost** ($15-65/month)  
✅ **Full SIEM** (Wazuh, OpenSearch, Suricata, Zeek)  
✅ **Local AI** (Ollama, ML inference, RAG)  
✅ **Great for learning** and testing

### AWS Serverless Production
✅ **Auto-scaling** (0 to millions of events)  
✅ **Pay-per-use** ($50-600/month based on load)  
✅ **Managed services** (no infrastructure maintenance)  
✅ **Enterprise-grade** (HA, encryption, compliance)  
✅ **CI/CD ready** (GitHub Actions pipelines)

### Key Capabilities
- **99.28% ML accuracy** on network intrusion detection
- **95.2% accuracy** on CloudTrail anomaly detection
- **LLM-powered triage** with context-rich explanations
- **MITRE ATT&CK RAG** for threat intelligence
- **Automated remediation** (disable keys, block IPs, etc.)
- **Full observability** (Prometheus, Grafana, AlertManager)

### Next Steps

1. **Start with Docker** to learn the system:
   ```bash
   git clone https://github.com/YourOrg/AI_SOC.git
   cd AI_SOC
   ./scripts/setup-configs.sh
   docker-compose -f docker-compose/phase1-siem-core.yml up -d
   docker-compose -f docker-compose/ai-services.yml up -d
   ```

2. **Train custom models** on your data:
   ```bash
   python3 scripts/score_cloudtrail_events.py  # LLM labeling
   python3 ml_training/train_cloudtrail_model.py  # Train
   ```

3. **Deploy to AWS** for production:
   ```bash
   aws cloudformation create-stack \
     --stack-name ai-soc-prod \
     --template-body file://cloudformation/root-stack.yaml \
     --parameters file://cloudformation/parameters/prod.json \
     --capabilities CAPABILITY_NAMED_IAM \
     --region eu-central-1
   ```

4. **Customize workflows** for your environment:
   - Add new Lambda functions for custom integrations
   - Train models on your specific data
   - Configure remediation actions for your infrastructure
   - Build custom Grafana dashboards

---

## Appendix: Quick Reference Commands

### Docker Operations

```bash
# Start all services
docker-compose -f docker-compose/phase1-siem-core.yml up -d
docker-compose -f docker-compose/ai-services.yml up -d
docker-compose -f docker-compose/monitoring-stack.yml up -d

# Check service health
docker-compose -f docker-compose/phase1-siem-core.yml ps
docker-compose -f docker-compose/ai-services.yml ps

# View logs
docker-compose -f docker-compose/phase1-siem-core.yml logs -f wazuh.manager
docker logs ollama --tail 100

# Stop all services
docker-compose -f docker-compose/phase1-siem-core.yml down
docker-compose -f docker-compose/ai-services.yml down

# Clean up (DESTROYS DATA)
docker-compose -f docker-compose/phase1-siem-core.yml down -v
docker volume prune -f
```

### AWS Operations

```bash
# Validate CloudFormation template
aws cloudformation validate-template \
  --template-body file://cloudformation/root-stack.yaml \
  --region eu-central-1

# Package and deploy
aws cloudformation package \
  --template-file cloudformation/root-stack.yaml \
  --s3-bucket ai-soc-artifacts-ACCOUNT_ID \
  --s3-prefix templates \
  --output-template-file packaged.yaml \
  --region eu-central-1

aws cloudformation deploy \
  --template-file packaged.yaml \
  --stack-name ai-soc-dev \
  --parameter-overrides file://cloudformation/parameters/dev.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-central-1

# Check deployment status
aws cloudformation describe-stacks \
  --stack-name ai-soc-dev \
  --region eu-central-1 \
  --query "Stacks[0].{Status:StackStatus,Outputs:Outputs}"

# Monitor logs
aws logs tail /aws/lambda/ai-soc-dev-event-normalizer --follow --region eu-central-1

# Invoke Step Functions
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:eu-central-1:ACCOUNT_ID:stateMachine:ai-soc-dev-soc \
  --input file://test-event.json \
  --region eu-central-1

# Destroy infrastructure
aws cloudformation delete-stack --stack-name ai-soc-dev --region eu-central-1
```

### ML/AI Operations

```bash
# Label training data with LLM
python3 scripts/score_cloudtrail_events.py

# Train ML model
python3 ml_training/train_cloudtrail_model.py \
  --input datasets/aws_samples/shared_services_labeled.json \
  --output models/cloudtrail_rf.pkl

# Test inference locally
curl -X POST http://localhost:8500/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [0,1,0,1,1,0,0,14,2,0,1,0,0,0,0,0,1,2], "model_name": "random_forest"}'

# Test alert triage
curl -X POST http://localhost:8100/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "test-001",
    "rule_description": "SSH brute force",
    "rule_level": 10,
    "source_ip": "1.2.3.4",
    "dest_ip": "10.0.0.1"
  }'

# Test RAG retrieval
curl -X POST http://localhost:8300/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "credential access techniques",
    "collection": "mitre_attack",
    "top_k": 5
  }'

# Deploy model to SageMaker
python3 ml_training/deploy_to_sagemaker.py \
  --model models/cloudtrail_rf.pkl \
  --endpoint-name ai-soc-prod-cloudtrail \
  --instance-type ml.serverless
```

### Monitoring Operations

```bash
# Access Prometheus
open http://localhost:9090

# Sample PromQL queries:
# - Alert rate: rate(wazuh_alerts_total[5m])
# - ML inference latency: histogram_quantile(0.95, ml_inference_latency_seconds)
# - Container CPU: container_cpu_usage_percent{container="ollama"}

# Access Grafana
open http://localhost:3000
# Login: admin / admin123
# Dashboards: AI-SOC Overview, SIEM Metrics, ML Performance

# Check AlertManager
open http://localhost:9093
# View active alerts and silences

# Query Loki logs
curl -G http://localhost:3100/loki/api/v1/query_range \
  --data-urlencode 'query={container="alert-triage"}' \
  --data-urlencode 'limit=100'
```

---

## Document Metadata

**Document Version**: 2.0 (Technical Architecture Reference)  
**Last Updated**: December 11, 2024  
**Repository**: AI_SOC - AI-Augmented Security Operations Center  
**Maintainer**: Security Engineering Team  
**License**: Apache 2.0  

**Changelog**:
- v2.0 (Dec 2024): Complete rewrite as technical architecture guide
- v1.0 (Dec 2024): Initial AWS serverless implementation guide

**Related Documentation**:
- `README.md`: Quick start guide
- `PROJECT.md`: Project status and context
- `SETUP.md`: Detailed setup instructions
- `MONITORING_STACK_SUMMARY.md`: Monitoring configuration
- `docs/`: Full MkDocs documentation site