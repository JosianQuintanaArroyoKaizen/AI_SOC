#!/usr/bin/env python3
"""
Train CloudTrail model using SageMaker Training Job
Uploads labeled data to S3 and creates a training job
"""

import boto3
import json
import time
from datetime import datetime

# Configuration
REGION = "eu-central-1"
PROJECT = "ai-soc"
ENV = "dev"
TRAINING_DATA_PATH = "datasets/aws_samples/train.json"
MODEL_NAME = "cloudtrail"
MODEL_VERSION = "2.0"

# Initialize clients
s3 = boto3.client("s3", region_name=REGION)
sagemaker = boto3.client("sagemaker", region_name=REGION)
sts = boto3.client("sts", region_name=REGION)

# Get account ID
account_id = sts.get_caller_identity()["Account"]
bucket_name = f"{PROJECT}-{ENV}-ml-training-{account_id}"

def ensure_s3_bucket():
    """Create S3 bucket if it doesn't exist"""
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"✅ Using existing bucket: {bucket_name}")
    except:
        print(f"📦 Creating bucket: {bucket_name}")
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": REGION}
            )
        print(f"✅ Created bucket: {bucket_name}")

def upload_training_data():
    """Upload training data to S3"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    s3_key = f"training-data/{MODEL_NAME}/{timestamp}/train.json"
    
    print(f"\n📤 Uploading training data to S3...")
    print(f"   Source: {TRAINING_DATA_PATH}")
    print(f"   Destination: s3://{bucket_name}/{s3_key}")
    
    s3.upload_file(TRAINING_DATA_PATH, bucket_name, s3_key)
    print(f"✅ Upload complete")
    
    return f"s3://{bucket_name}/{s3_key}"

def get_or_create_role():
    """Get or create SageMaker execution role"""
    role_name = f"{PROJECT}-{ENV}-sagemaker-role"
    iam = boto3.client("iam", region_name=REGION)
    
    try:
        response = iam.get_role(RoleName=role_name)
        role_arn = response["Role"]["Arn"]
        print(f"✅ Using existing role: {role_arn}")
        return role_arn
    except iam.exceptions.NoSuchEntityException:
        print(f"⚠️  Role {role_name} not found")
        print(f"   Using default SageMaker execution role")
        # Try to use the role created by deploy_to_sagemaker.py
        return f"arn:aws:iam::{account_id}:role/{role_name}"

def create_training_job(training_data_uri):
    """Create SageMaker training job"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_name = f"{PROJECT}-{ENV}-{MODEL_NAME}-{timestamp}"
    output_path = f"s3://{bucket_name}/models/{MODEL_NAME}/{timestamp}"
    
    role_arn = get_or_create_role()
    
    print(f"\n🎯 Creating SageMaker training job...")
    print(f"   Job Name: {job_name}")
    print(f"   Training Data: {training_data_uri}")
    print(f"   Output: {output_path}")
    
    # Use sklearn built-in algorithm
    training_image = sagemaker.describe_algorithm(AlgorithmName="sklearn")["TrainingImage"]
    
    training_params = {
        "TrainingJobName": job_name,
        "RoleArn": role_arn,
        "AlgorithmSpecification": {
            "TrainingImage": f"683313688378.dkr.ecr.{REGION}.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3",
            "TrainingInputMode": "File",
            "EnableSageMakerMetricsTimeSeries": True
        },
        "InputDataConfig": [
            {
                "ChannelName": "training",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": training_data_uri.rsplit("/", 1)[0],  # Directory containing train.json
                        "S3DataDistributionType": "FullyReplicated"
                    }
                },
                "ContentType": "application/json"
            }
        ],
        "OutputDataConfig": {
            "S3OutputPath": output_path
        },
        "ResourceConfig": {
            "InstanceType": "ml.m5.large",
            "InstanceCount": 1,
            "VolumeSizeInGB": 30
        },
        "StoppingCondition": {
            "MaxRuntimeInSeconds": 3600  # 1 hour max
        },
        "HyperParameters": {
            "model_type": "random_forest",
            "n_estimators": "100",
            "max_depth": "20",
            "use_llm_labels": "true"  # Use llm_severity from labeled data
        }
    }
    
    try:
        response = sagemaker.create_training_job(**training_params)
        print(f"✅ Training job created: {job_name}")
        return job_name
    except Exception as e:
        print(f"❌ Error creating training job: {e}")
        print(f"\n⚠️  Note: SageMaker training requires:")
        print(f"   1. Proper IAM role with SageMaker permissions")
        print(f"   2. Training script uploaded to S3")
        print(f"   3. Training image (sklearn or custom)")
        print(f"\n💡 For now, we'll train locally instead...")
        return None

def monitor_training_job(job_name):
    """Monitor training job progress"""
    if not job_name:
        return False
    
    print(f"\n⏳ Monitoring training job: {job_name}")
    
    while True:
        response = sagemaker.describe_training_job(TrainingJobName=job_name)
        status = response["TrainingJobStatus"]
        
        if status in ["Completed", "Failed", "Stopped"]:
            print(f"\n{'✅' if status == 'Completed' else '❌'} Training job {status}")
            if status == "Completed":
                print(f"   Model artifact: {response['ModelArtifacts']['S3ModelArtifacts']}")
            elif status == "Failed":
                print(f"   Failure reason: {response.get('FailureReason', 'Unknown')}")
            return status == "Completed"
        
        print(f"   Status: {status}...", end="\r")
        time.sleep(30)

def main():
    print("🤖 SageMaker Training Job Creator")
    print("=" * 60)
    
    # Step 1: Ensure S3 bucket exists
    ensure_s3_bucket()
    
    # Step 2: Upload training data
    training_data_uri = upload_training_data()
    
    # Step 3: Create training job
    job_name = create_training_job(training_data_uri)
    
    if job_name:
        # Step 4: Monitor training
        success = monitor_training_job(job_name)
        
        if success:
            print("\n🎉 Training completed successfully!")
            print(f"   Next steps:")
            print(f"   1. Deploy model to endpoint")
            print(f"   2. Update Lambda inference function")
            print(f"   3. Test with CloudTrail events")
        else:
            print("\n⚠️  Training did not complete successfully")
    else:
        print("\n⚠️  Training job not created - will train locally instead")
        print(f"   Run: python3 ml_training/train_cloudtrail_model.py --input {TRAINING_DATA_PATH}")

if __name__ == "__main__":
    main()
