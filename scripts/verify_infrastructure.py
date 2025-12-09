#!/usr/bin/env python3
"""
Verify AI-SOC Infrastructure
============================
Quick health check for your AI-SOC deployment

Usage: python3 scripts/verify_infrastructure.py
"""

import sys
import boto3
from botocore.exceptions import ClientError

# Configuration
PROJECT_NAME = "ai-soc"
ENVIRONMENT = "dev"
REGION = "eu-central-1"

def check_dynamodb():
    """Check if DynamoDB table exists"""
    print("📊 Checking DynamoDB...")
    try:
        dynamodb = boto3.client("dynamodb", region_name=REGION)
        table_name = f"{PROJECT_NAME}-{ENVIRONMENT}-state"
        response = dynamodb.describe_table(TableName=table_name)
        item_count = response["Table"]["ItemCount"]
        print(f"   ✅ Table '{table_name}' exists with {item_count} items")
        return True
    except ClientError as e:
        print(f"   ❌ Error: {e.response['Error']['Message']}")
        return False

def check_step_functions():
    """Check if Step Functions state machine exists"""
    print("\n⚙️  Checking Step Functions...")
    try:
        sfn = boto3.client("stepfunctions", region_name=REGION)
        response = sfn.list_state_machines()
        
        state_machine_name = f"{PROJECT_NAME}-{ENVIRONMENT}-soc-workflow"
        found = False
        
        for sm in response["stateMachines"]:
            if state_machine_name in sm["name"]:
                print(f"   ✅ State machine '{sm['name']}' found")
                print(f"      ARN: {sm['stateMachineArn']}")
                
                # Check recent executions
                executions = sfn.list_executions(
                    stateMachineArn=sm["stateMachineArn"],
                    maxResults=5
                )
                print(f"      Recent executions: {len(executions['executions'])}")
                found = True
                break
        
        if not found:
            print(f"   ⚠️  State machine '{state_machine_name}' not found")
            print("      Available state machines:")
            for sm in response["stateMachines"]:
                print(f"        - {sm['name']}")
        
        return found
    except ClientError as e:
        print(f"   ❌ Error: {e.response['Error']['Message']}")
        return False

def check_lambda_functions():
    """Check if Lambda functions exist"""
    print("\n🔧 Checking Lambda Functions...")
    lambda_client = boto3.client("lambda", region_name=REGION)
    
    functions_to_check = [
        "event-normalizer",
        "ml-inference",
        "alert-triage",
        "remediation",
        "bedrock-analysis",
    ]
    
    found_count = 0
    for func_suffix in functions_to_check:
        func_name = f"{PROJECT_NAME}-{ENVIRONMENT}-{func_suffix}"
        try:
            response = lambda_client.get_function(FunctionName=func_name)
            print(f"   ✅ {func_name}")
            found_count += 1
        except ClientError:
            print(f"   ⚠️  {func_name} not found")
    
    return found_count > 0

def check_eventbridge_rules():
    """Check if EventBridge rules exist"""
    print("\n📡 Checking EventBridge Rules...")
    events = boto3.client("events", region_name=REGION)
    
    rules_to_check = [
        f"{PROJECT_NAME}-{ENVIRONMENT}-guardduty-findings",
        f"{PROJECT_NAME}-{ENVIRONMENT}-securityhub-findings",
    ]
    
    found_count = 0
    for rule_name in rules_to_check:
        try:
            response = events.describe_rule(Name=rule_name)
            state = response["State"]
            print(f"   ✅ {rule_name} ({state})")
            found_count += 1
        except ClientError:
            print(f"   ⚠️  {rule_name} not found")
    
    return found_count > 0

def check_kinesis():
    """Check if Kinesis stream exists"""
    print("\n🌊 Checking Kinesis Stream...")
    try:
        kinesis = boto3.client("kinesis", region_name=REGION)
        stream_name = f"{PROJECT_NAME}-{ENVIRONMENT}-security-events"
        response = kinesis.describe_stream(StreamName=stream_name)
        status = response["StreamDescription"]["StreamStatus"]
        print(f"   ✅ Stream '{stream_name}' status: {status}")
        return True
    except ClientError as e:
        print(f"   ⚠️  Stream not found or error: {e.response['Error']['Message']}")
        return False

def main():
    print("=" * 60)
    print("AI-SOC Infrastructure Health Check")
    print("=" * 60)
    
    results = {
        "DynamoDB": check_dynamodb(),
        "Step Functions": check_step_functions(),
        "Lambda Functions": check_lambda_functions(),
        "EventBridge": check_eventbridge_rules(),
        "Kinesis": check_kinesis(),
    }
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    for component, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {component}")
    
    all_good = all(results.values())
    
    if all_good:
        print("\n✅ All components are deployed and accessible!")
        print("\n🚀 Ready to inject test events:")
        print("   python3 scripts/inject_test_events.py --count 5")
    else:
        print("\n⚠️  Some components are missing or inaccessible.")
        print("\n💡 To deploy the infrastructure:")
        print("   aws cloudformation deploy --template-file cloudformation/root-stack.yaml \\")
        print("       --stack-name ai-soc-dev --parameter-overrides ...")
    
    print()
    return 0 if all_good else 1

if __name__ == "__main__":
    sys.exit(main())
