#!/usr/bin/env python3
"""
Deploy CICIDS2017 IDS Model to SageMaker

This script packages the trained model and deploys it to AWS SageMaker
for real-time inference in the AI-SOC pipeline.

Usage:
    python3 deploy_to_sagemaker.py --model random_forest --instance-type ml.t2.medium

Author: AI-SOC Team
Date: 2025-12-10
"""

import argparse
import boto3
import json
import os
import pickle
import tarfile
import time
from pathlib import Path
from datetime import datetime

# Configuration
PROJECT_NAME = "ai-soc"
ENVIRONMENT = "dev"
REGION = "eu-central-1"
# Use absolute path relative to script location
SCRIPT_DIR = Path(__file__).parent
MODEL_DIR = SCRIPT_DIR.parent / "models"
PACKAGE_DIR = Path("sagemaker_model")

# Initialize AWS clients
s3_client = boto3.client("s3", region_name=REGION)
sagemaker_client = boto3.client("sagemaker", region_name=REGION)
iam_client = boto3.client("iam", region_name=REGION)
sts_client = boto3.client("sts", region_name=REGION)


def get_or_create_sagemaker_role():
    """Get or create IAM role for SageMaker"""
    role_name = f"{PROJECT_NAME}-{ENVIRONMENT}-sagemaker-role"
    
    try:
        response = iam_client.get_role(RoleName=role_name)
        role_arn = response["Role"]["Arn"]
        print(f"✅ Using existing SageMaker role: {role_arn}")
        return role_arn
    except iam_client.exceptions.NoSuchEntityException:
        print(f"📝 Creating SageMaker role: {role_name}")
        
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "sagemaker.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=f"SageMaker execution role for {PROJECT_NAME}"
        )
        role_arn = response["Role"]["Arn"]
        
        # Attach necessary policies
        policies = [
            "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess",
            "arn:aws:iam::aws:policy/AmazonS3FullAccess"
        ]
        
        for policy in policies:
            iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy)
        
        print(f"⏳ Waiting 10 seconds for role to propagate...")
        time.sleep(10)
        
        print(f"✅ Created SageMaker role: {role_arn}")
        return role_arn


def create_inference_script():
    """Create SageMaker inference script"""
    inference_code = '''
import json
import pickle
import numpy as np
import os

def model_fn(model_dir):
    """Load model and preprocessing artifacts"""
    models = {}
    scaler = None
    label_encoder = None
    
    # Load model
    model_path = os.path.join(model_dir, "model.pkl")
    with open(model_path, "rb") as f:
        models["model"] = pickle.load(f)
    
    # Load scaler
    scaler_path = os.path.join(model_dir, "scaler.pkl")
    if os.path.exists(scaler_path):
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
    
    # Load label encoder
    encoder_path = os.path.join(model_dir, "label_encoder.pkl")
    if os.path.exists(encoder_path):
        with open(encoder_path, "rb") as f:
            label_encoder = pickle.load(f)
    
    return {
        "model": models["model"],
        "scaler": scaler,
        "label_encoder": label_encoder
    }


def input_fn(request_body, content_type="application/json"):
    """Parse input data"""
    if content_type == "application/json":
        data = json.loads(request_body)
        features = np.array(data["features"]).reshape(1, -1)
        return features
    else:
        raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(input_data, model_dict):
    """Run prediction"""
    model = model_dict["model"]
    scaler = model_dict["scaler"]
    label_encoder = model_dict["label_encoder"]
    
    # Scale features
    if scaler is not None:
        input_data = scaler.transform(input_data)
    
    # Make prediction
    prediction = model.predict(input_data)[0]
    
    # Get probabilities if available
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(input_data)[0]
    else:
        proba = None
    
    # Decode label
    if label_encoder is not None:
        prediction_label = label_encoder.inverse_transform([prediction])[0]
    else:
        prediction_label = str(prediction)
    
    return {
        "prediction": prediction_label,
        "confidence": float(max(proba)) if proba is not None else 1.0,
        "probabilities": {label_encoder.classes_[i]: float(proba[i]) for i in range(len(proba))} if proba is not None and label_encoder is not None else {}
    }


def output_fn(prediction, accept="application/json"):
    """Format output"""
    if accept == "application/json":
        return json.dumps(prediction), accept
    else:
        raise ValueError(f"Unsupported accept type: {accept}")
'''
    
    script_path = PACKAGE_DIR / "inference.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    with open(script_path, "w") as f:
        f.write(inference_code)
    
    print(f"✅ Created inference script: {script_path}")
    return script_path


def package_model(model_name):
    """Package model for SageMaker"""
    print(f"\n📦 Packaging model: {model_name}")
    
    # Create package directory
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create inference script
    create_inference_script()
    
    # Copy model artifacts
    # Handle both CICIDS2017 models (with _ids suffix) and CloudTrail models (without suffix)
    model_file = MODEL_DIR / f"{model_name}.pkl"
    if not model_file.exists():
        model_file = MODEL_DIR / f"{model_name}_ids.pkl"
    
    # Handle different scaler/encoder naming conventions
    if model_name.startswith("cloudtrail"):
        scaler_file = MODEL_DIR / "cloudtrail_scaler.pkl"
        encoder_file = MODEL_DIR / "cloudtrail_label_encoder.pkl"
    else:
        scaler_file = MODEL_DIR / "scaler.pkl"
        encoder_file = MODEL_DIR / "label_encoder.pkl"
    
    if not model_file.exists():
        raise FileNotFoundError(f"Model not found: {model_file}")
    
    # Copy to package directory with standard names
    import shutil
    shutil.copy(model_file, PACKAGE_DIR / "model.pkl")
    if scaler_file.exists():
        shutil.copy(scaler_file, PACKAGE_DIR / "scaler.pkl")
    if encoder_file.exists():
        shutil.copy(encoder_file, PACKAGE_DIR / "label_encoder.pkl")
    
    # Create model.tar.gz
    tar_path = Path("model.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        for file in PACKAGE_DIR.iterdir():
            tar.add(file, arcname=file.name)
    
    print(f"✅ Model packaged: {tar_path}")
    return tar_path


def upload_to_s3(tar_path, bucket_name):
    """Upload model package to S3"""
    account_id = sts_client.get_caller_identity()["Account"]
    bucket_name = bucket_name or f"{PROJECT_NAME}-{ENVIRONMENT}-models-{account_id}"
    
    # Create bucket if it doesn't exist
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ Using existing S3 bucket: {bucket_name}")
    except:
        print(f"📝 Creating S3 bucket: {bucket_name}")
        if REGION == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": REGION}
            )
    
    # Upload model
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    s3_key = f"models/{timestamp}/model.tar.gz"
    
    print(f"⬆️  Uploading to s3://{bucket_name}/{s3_key}")
    s3_client.upload_file(str(tar_path), bucket_name, s3_key)
    
    s3_uri = f"s3://{bucket_name}/{s3_key}"
    print(f"✅ Model uploaded: {s3_uri}")
    return s3_uri


def build_and_push_custom_container():
    """Build and push custom Docker container with correct scikit-learn version"""
    print("\n🐳 Building custom Docker container with scikit-learn 1.7.2...")
    
    # Create Dockerfile
    dockerfile_content = '''FROM python:3.11-slim

RUN pip install --no-cache-dir \
    scikit-learn==1.7.2 \
    numpy==2.2.1 \
    xgboost==2.1.3 \
    flask \
    gunicorn \
    sagemaker-inference

# Copy inference code
COPY inference.py /opt/program/inference.py

ENV PATH="/opt/program:${PATH}"
ENV SAGEMAKER_PROGRAM=inference.py

WORKDIR /opt/program

# Set up SageMaker inference
ENTRYPOINT ["python", "-m", "sagemaker_inference", "serve"]
'''
    
    dockerfile_path = PACKAGE_DIR / "Dockerfile"
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)
    
    print(f"✅ Dockerfile created")
    
    # Get ECR repository name
    account_id = sts_client.get_caller_identity()["Account"]
    ecr_repo_name = f"{PROJECT_NAME}-{ENVIRONMENT}-ml-inference"
    ecr_uri = f"{account_id}.dkr.ecr.{REGION}.amazonaws.com/{ecr_repo_name}"
    
    # Create ECR repository if it doesn't exist
    ecr_client = boto3.client("ecr", region_name=REGION)
    try:
        ecr_client.describe_repositories(repositoryNames=[ecr_repo_name])
        print(f"✅ Using existing ECR repository: {ecr_repo_name}")
    except ecr_client.exceptions.RepositoryNotFoundException:
        print(f"📝 Creating ECR repository: {ecr_repo_name}")
        ecr_client.create_repository(
            repositoryName=ecr_repo_name,
            imageScanningConfiguration={'scanOnPush': True}
        )
    
    # Get ECR login
    print("🔐 Logging into ECR...")
    auth_response = ecr_client.get_authorization_token()
    auth_data = auth_response['authorizationData'][0]
    auth_token = auth_data['authorizationToken']
    
    import base64
    username, password = base64.b64decode(auth_token).decode().split(':')
    
    # Build Docker image
    print("🔨 Building Docker image (this may take a few minutes)...")
    import subprocess
    
    build_cmd = [
        "docker", "build",
        "-t", ecr_uri + ":latest",
        "-f", str(dockerfile_path),
        str(PACKAGE_DIR)
    ]
    
    result = subprocess.run(build_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Docker build output: {result.stdout}")
        print(f"Docker build errors: {result.stderr}")
        raise RuntimeError(f"Docker build failed: {result.stderr}")
    
    print("✅ Docker image built")
    
    # Login to ECR
    login_cmd = f"echo {password} | docker login --username {username} --password-stdin {account_id}.dkr.ecr.{REGION}.amazonaws.com"
    result = subprocess.run(login_cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ECR login failed: {result.stderr}")
    
    # Push to ECR
    print(f"⬆️  Pushing image to ECR...")
    push_cmd = ["docker", "push", ecr_uri + ":latest"]
    result = subprocess.run(push_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Docker push failed: {result.stderr}")
    
    print(f"✅ Image pushed to ECR: {ecr_uri}:latest")
    return ecr_uri + ":latest"


def create_sagemaker_model_with_prebuilt_container(model_name, s3_uri, role_arn):
    """Create SageMaker model using prebuilt inference container"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    model_name_clean = model_name.replace("_", "-")
    model_name_sm = f"{PROJECT_NAME}-{ENVIRONMENT}-{model_name_clean}-{timestamp}"
    
    print(f"\n📝 Creating SageMaker model: {model_name_sm}")
    
    # Use PyTorch inference container with Python 3.11 (has newer dependencies)
    account_mappings = {
        "eu-central-1": "763104351884",
        "us-east-1": "763104351884",
        "us-west-2": "763104351884"
    }
    account = account_mappings.get(REGION, "763104351884")
    # Use PyTorch inference container which has better scikit-learn support
    container_uri = f"{account}.dkr.ecr.{REGION}.amazonaws.com/pytorch-inference:2.1-cpu-py310"
    
    response = sagemaker_client.create_model(
        ModelName=model_name_sm,
        PrimaryContainer={
            "Image": container_uri,
            "ModelDataUrl": s3_uri,
            "Environment": {
                "SAGEMAKER_PROGRAM": "inference.py",
                "SAGEMAKER_SUBMIT_DIRECTORY": s3_uri
            }
        },
        ExecutionRoleArn=role_arn
    )
    
    print(f"✅ SageMaker model created: {model_name_sm}")
    return model_name_sm


def create_sagemaker_model(model_name, s3_uri, role_arn, container_uri):
    """Create SageMaker model"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Replace underscores with hyphens for SageMaker naming rules
    model_name_clean = model_name.replace("_", "-")
    model_name_sm = f"{PROJECT_NAME}-{ENVIRONMENT}-{model_name_clean}-{timestamp}"
    
    print(f"\n📝 Creating SageMaker model: {model_name_sm}")
    
    response = sagemaker_client.create_model(
        ModelName=model_name_sm,
        PrimaryContainer={
            "Image": container_uri,
            "ModelDataUrl": s3_uri,
        },
        ExecutionRoleArn=role_arn
    )
    
    print(f"✅ SageMaker model created: {model_name_sm}")
    return model_name_sm


def create_endpoint_config(model_name_sm, instance_type):
    """Create SageMaker endpoint configuration"""
    config_name = f"{model_name_sm}-config"
    
    print(f"\n📝 Creating endpoint configuration: {config_name}")
    
    response = sagemaker_client.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[
            {
                "VariantName": "AllTraffic",
                "ModelName": model_name_sm,
                "InitialInstanceCount": 1,
                "InstanceType": instance_type,
                "InitialVariantWeight": 1.0
            }
        ]
    )
    
    print(f"✅ Endpoint configuration created: {config_name}")
    return config_name


def create_endpoint(config_name):
    """Create SageMaker endpoint"""
    endpoint_name = f"{PROJECT_NAME}-{ENVIRONMENT}-ids-endpoint"
    
    # Delete existing endpoint if it exists
    try:
        sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
        print(f"🗑️  Deleting existing endpoint: {endpoint_name}")
        sagemaker_client.delete_endpoint(EndpointName=endpoint_name)
        time.sleep(30)
    except:
        pass
    
    print(f"\n📝 Creating endpoint: {endpoint_name}")
    print(f"⏳ This will take 5-10 minutes...")
    
    response = sagemaker_client.create_endpoint(
        EndpointName=endpoint_name,
        EndpointConfigName=config_name
    )
    
    # Wait for endpoint to be in service
    print("⏳ Waiting for endpoint to be InService...")
    waiter = sagemaker_client.get_waiter("endpoint_in_service")
    waiter.wait(EndpointName=endpoint_name)
    
    print(f"✅ Endpoint created and InService: {endpoint_name}")
    return endpoint_name


def update_lambda_env(endpoint_name):
    """Update Lambda function environment variable"""
    lambda_client = boto3.client("lambda", region_name=REGION)
    function_name = f"{PROJECT_NAME}-{ENVIRONMENT}-ml-inference"
    
    print(f"\n📝 Updating Lambda function: {function_name}")
    
    try:
        response = lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment={
                "Variables": {
                    "SAGEMAKER_ENDPOINT": endpoint_name
                }
            }
        )
        print(f"✅ Lambda environment updated with SAGEMAKER_ENDPOINT={endpoint_name}")
    except Exception as e:
        print(f"⚠️  Could not update Lambda automatically: {e}")
        print(f"   Please manually set SAGEMAKER_ENDPOINT={endpoint_name} in Lambda console")


def main():
    parser = argparse.ArgumentParser(description="Deploy IDS model to SageMaker")
    parser.add_argument("--model", default="random_forest", 
                        choices=["random_forest", "xgboost", "decision_tree", "cloudtrail_random_forest"],
                        help="Model to deploy")
    parser.add_argument("--instance-type", default="ml.t2.medium",
                        help="SageMaker instance type for endpoint")
    parser.add_argument("--bucket", help="S3 bucket name (optional, will create if not specified)")
    parser.add_argument("--no-docker", action="store_true", help="Skip Docker build and use prebuilt container")
    
    args = parser.parse_args()
    
    print(f"\n🚀 Deploying {args.model} model to SageMaker")
    print(f"   Region: {REGION}")
    print(f"   Instance Type: {args.instance_type}")
    if args.no_docker:
        print(f"   Mode: Using prebuilt PyTorch container")
    
    if args.no_docker:
        print(f"   Mode: Using prebuilt PyTorch container")
    else:
        print(f"   Mode: Building custom container with scikit-learn 1.7.2")
    print()
    
    try:
        # Step 1: Get/Create IAM role
        role_arn = get_or_create_sagemaker_role()
        
        # Step 2: Package model
        tar_path = package_model(args.model)
        
        # Step 3: Upload to S3
        s3_uri = upload_to_s3(tar_path, args.bucket)
        
        # Step 4 & 5: Create SageMaker model (with or without custom container)
        if args.no_docker:
            model_name_sm = create_sagemaker_model_with_prebuilt_container(args.model, s3_uri, role_arn)
        else:
            container_uri = build_and_push_custom_container()
            model_name_sm = create_sagemaker_model(args.model, s3_uri, role_arn, container_uri)
        
        # Step 6: Create endpoint configuration
        config_name = create_endpoint_config(model_name_sm, args.instance_type)
        
        # Step 7: Create endpoint
        endpoint_name = create_endpoint(config_name)
        
        # Step 8: Update Lambda
        update_lambda_env(endpoint_name)
        
        print(f"\n✅ Deployment complete!")
        print(f"   Endpoint Name: {endpoint_name}")
        print(f"   Model: {args.model}")
        print(f"   Instance: {args.instance_type}")
        print(f"\n💡 You can now test the pipeline with CloudTrail events!")
        
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        raise


if __name__ == "__main__":
    main()
