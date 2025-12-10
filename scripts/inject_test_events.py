#!/usr/bin/env python3
"""
Inject Test Security Events
============================
This script injects realistic test events into the AI-SOC pipeline to demonstrate
the complete flow from event generation to DynamoDB storage.

Usage:
    python3 scripts/inject_test_events.py --count 5
    python3 scripts/inject_test_events.py --severity CRITICAL --count 3
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
import random

import boto3
from botocore.exceptions import ClientError

# Configuration
PROJECT_NAME = "ai-soc"
ENVIRONMENT = "dev"
REGION = "eu-central-1"

# Initialize AWS clients
events_client = boto3.client("events", region_name=REGION)
stepfunctions_client = boto3.client("stepfunctions", region_name=REGION)

# Test event templates
GUARDDUTY_TEMPLATES = [
    {
        "type": "UnauthorizedAccess:IAMUser/MaliciousIPCaller.Custom",
        "severity": 8.0,
        "title": "API call from malicious IP address",
        "description": "An API call was invoked from a known malicious IP address.",
        "resource_type": "AccessKey",
    },
    {
        "type": "Recon:EC2/PortProbeUnprotectedPort",
        "severity": 7.5,
        "title": "Unprotected port on EC2 instance is being probed",
        "description": "EC2 instance has an unprotected port being probed by a known malicious host.",
        "resource_type": "Instance",
    },
    {
        "type": "Trojan:EC2/BlackholeTraffic",
        "severity": 8.5,
        "title": "EC2 instance is attempting to communicate with an IP address of a black hole",
        "description": "EC2 instance is attempting to communicate with an IP address of a remote host that is a known black hole.",
        "resource_type": "Instance",
    },
    {
        "type": "Backdoor:EC2/C&CActivity.B",
        "severity": 9.0,
        "title": "EC2 instance is querying a domain name associated with a known Command & Control server",
        "description": "EC2 instance is querying a domain name associated with a known Command & Control server.",
        "resource_type": "Instance",
    },
    {
        "type": "CryptoCurrency:EC2/BitcoinTool.B",
        "severity": 6.5,
        "title": "EC2 instance is querying an IP address associated with cryptocurrency-related activity",
        "description": "EC2 instance is querying an IP address that is associated with Bitcoin or other cryptocurrency-related activity.",
        "resource_type": "Instance",
    },
]

SECURITYHUB_TEMPLATES = [
    {
        "title": "IAM policy allows full administrative privileges",
        "severity": 90,
        "type": "Software and Configuration Checks/AWS Security Best Practices",
        "description": "An IAM policy grants full administrative privileges which violates the principle of least privilege.",
    },
    {
        "title": "S3 bucket has public read access enabled",
        "severity": 70,
        "type": "Software and Configuration Checks/AWS Security Best Practices",
        "description": "An S3 bucket allows public read access which may expose sensitive data.",
    },
    {
        "title": "Security group allows unrestricted ingress on port 22",
        "severity": 60,
        "type": "Software and Configuration Checks/AWS Security Best Practices",
        "description": "A security group rule allows unrestricted SSH access from any IP address.",
    },
]


def create_guardduty_event(template, custom_severity=None):
    """Create a GuardDuty finding event"""
    now = datetime.utcnow()
    event_id = f"test-gd-{random.randint(10000, 99999)}"
    
    severity = custom_severity if custom_severity else template["severity"]
    
    return {
        "version": "0",
        "id": event_id,
        "detail-type": "GuardDuty Finding",
        "source": "aws.guardduty",
        "account": boto3.client("sts").get_caller_identity()["Account"],
        "time": now.isoformat() + "Z",
        "region": REGION,
        "resources": [],
        "detail": {
            "schemaVersion": "2.0",
            "accountId": boto3.client("sts").get_caller_identity()["Account"],
            "region": REGION,
            "partition": "aws",
            "id": event_id,
            "arn": f"arn:aws:guardduty:{REGION}:123456789012:detector/test/finding/{event_id}",
            "type": template["type"],
            "resource": {
                "resourceType": template["resource_type"],
                "instanceDetails": {
                    "instanceId": f"i-{random.randint(100000000000, 999999999999):012x}",
                    "instanceType": random.choice(["t2.micro", "t3.small", "m5.large"]),
                    "launchTime": (now - timedelta(days=random.randint(1, 30))).isoformat() + "Z",
                    "tags": [{"key": "Environment", "value": "production"}],
                }
            },
            "service": {
                "serviceName": "guardduty",
                "detectorId": "test-detector",
                "action": {
                    "actionType": "NETWORK_CONNECTION",
                    "networkConnectionAction": {
                        "connectionDirection": "OUTBOUND",
                        "remoteIpDetails": {
                            "ipAddressV4": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
                            "country": {"countryName": random.choice(["Russia", "China", "Ukraine", "Romania"])},
                        },
                        "protocol": "TCP",
                        "localPortDetails": {"port": random.choice([22, 443, 3389, 8080])},
                    },
                },
                "eventFirstSeen": (now - timedelta(minutes=30)).isoformat() + "Z",
                "eventLastSeen": now.isoformat() + "Z",
                "archived": False,
                "count": random.randint(1, 10),
            },
            "severity": severity,
            "createdAt": (now - timedelta(minutes=30)).isoformat() + "Z",
            "updatedAt": now.isoformat() + "Z",
            "title": template["title"],
            "description": template["description"],
        },
    }


def create_securityhub_event(template, custom_severity=None):
    """Create a Security Hub finding event"""
    now = datetime.utcnow()
    event_id = f"test-sh-{random.randint(10000, 99999)}"
    
    severity = custom_severity if custom_severity else template["severity"]
    
    return {
        "version": "0",
        "id": event_id,
        "detail-type": "Security Hub Findings - Imported",
        "source": "aws.securityhub",
        "account": boto3.client("sts").get_caller_identity()["Account"],
        "time": now.isoformat() + "Z",
        "region": REGION,
        "resources": [],
        "detail": {
            "findings": [
                {
                    "SchemaVersion": "2018-10-08",
                    "Id": f"arn:aws:securityhub:{REGION}:123456789012:subscription/test/finding/{event_id}",
                    "ProductArn": f"arn:aws:securityhub:{REGION}::product/aws/securityhub",
                    "GeneratorId": "aws-foundational-security-best-practices",
                    "AwsAccountId": boto3.client("sts").get_caller_identity()["Account"],
                    "Types": [template["type"]],
                    "CreatedAt": (now - timedelta(minutes=30)).isoformat() + "Z",
                    "UpdatedAt": now.isoformat() + "Z",
                    "Severity": {
                        "Product": severity / 10,
                        "Label": get_severity_label(severity),
                        "Normalized": severity,
                    },
                    "Title": template["title"],
                    "Description": template["description"],
                    "Resources": [
                        {
                            "Type": "AwsIamPolicy" if "IAM" in template["title"] else "AwsEc2SecurityGroup",
                            "Id": f"arn:aws:iam::123456789012:policy/test-policy-{random.randint(100, 999)}",
                            "Partition": "aws",
                            "Region": REGION,
                        }
                    ],
                    "WorkflowState": "NEW",
                    "Workflow": {"Status": "NEW"},
                    "RecordState": "ACTIVE",
                }
            ]
        },
    }


def get_severity_label(normalized_score):
    """Convert normalized severity score to label"""
    if normalized_score >= 90:
        return "CRITICAL"
    elif normalized_score >= 70:
        return "HIGH"
    elif normalized_score >= 40:
        return "MEDIUM"
    elif normalized_score >= 1:
        return "LOW"
    return "INFORMATIONAL"


def inject_event_via_eventbridge(event):
    """Send event to EventBridge"""
    try:
        response = events_client.put_events(Entries=[event])
        
        if response["FailedEntryCount"] > 0:
            print(f"❌ Failed to inject event: {response['Entries'][0].get('ErrorMessage')}")
            return False
        
        print(f"✅ Injected {event['source']} event: {event['id']}")
        return True
    
    except ClientError as e:
        print(f"❌ Error injecting event: {e}")
        return False


def inject_event_via_stepfunctions(event):
    """
    Directly invoke Step Functions workflow (alternative method if EventBridge doesn't work)
    """
    try:
        # Get the state machine ARN
        state_machine_name = f"{PROJECT_NAME}-{ENVIRONMENT}-soc-workflow"
        
        # Create normalized event format (as if it came through event-normalizer)
        normalized_event = {
            "event_id": event["id"],
            "timestamp": event["time"],
            "source": event["source"],
            "account_id": event["account"],
            "region": event["region"],
            "event_type": event["detail-type"],
            "severity": extract_severity(event["detail"], event["source"]),
            "raw_event": event["detail"],
            # Add mock ML prediction
            "ml_prediction": {
                "threat_score": random.uniform(60, 95),
                "model_version": "1.0",
                "evaluated_at": datetime.utcnow().isoformat(),
            },
        }
        
        # List state machines to find ours
        response = stepfunctions_client.list_state_machines()
        state_machine_arn = None
        
        for sm in response["stateMachines"]:
            if state_machine_name in sm["name"]:
                state_machine_arn = sm["stateMachineArn"]
                break
        
        if not state_machine_arn:
            print(f"⚠️  State machine '{state_machine_name}' not found")
            return False
        
        # Start execution
        execution_response = stepfunctions_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"test-{event['id']}-{int(datetime.utcnow().timestamp())}",
            input=json.dumps(normalized_event),
        )
        
        print(f"✅ Started Step Functions execution: {execution_response['executionArn']}")
        return True
    
    except ClientError as e:
        print(f"❌ Error invoking Step Functions: {e}")
        return False


def extract_severity(detail, source):
    """Extract severity from event detail"""
    if source == "aws.guardduty":
        severity_score = detail.get("severity", 0)
        if severity_score >= 7:
            return "HIGH"
        elif severity_score >= 4:
            return "MEDIUM"
        return "LOW"
    elif source == "aws.securityhub":
        normalized = detail.get("findings", [{}])[0].get("Severity", {}).get("Normalized", 0)
        if normalized >= 70:
            return "HIGH"
        elif normalized >= 40:
            return "MEDIUM"
        return "LOW"
    return "MEDIUM"


def main():
    parser = argparse.ArgumentParser(description="Inject test security events into AI-SOC pipeline")
    parser.add_argument("--count", type=int, default=5, help="Number of synthetic events to inject")
    parser.add_argument("--severity", choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"], help="Override severity for all events")
    parser.add_argument("--method", choices=["eventbridge", "stepfunctions", "both"], default="eventbridge", help="Injection method (default: eventbridge for full pipeline)")
    parser.add_argument("--source", choices=["guardduty", "securityhub", "mixed"], default="mixed", help="Event source type for synthetic events")
    parser.add_argument("--from-file", type=str, help="Path to JSON file with real CloudTrail/GuardDuty events to inject")

    args = parser.parse_args()

    severity_map = {"LOW": 3.0, "MEDIUM": 5.0, "HIGH": 7.5, "CRITICAL": 9.5}
    custom_severity = severity_map.get(args.severity) if args.severity else None

    # If --from-file is provided, inject real events from file via EventBridge
    if args.from_file:
        print(f"\n🚀 Injecting events from {args.from_file} via EventBridge (full pipeline)...\n")
        try:
            with open(args.from_file, "r") as f:
                data = json.load(f)
            
            # Handle CloudTrail export format with "Records" wrapper
            if isinstance(data, dict) and "Records" in data:
                events = data["Records"]
                print(f"📦 Found {len(events)} CloudTrail events in Records array")
            elif isinstance(data, list):
                events = data
                print(f"📦 Found {len(events)} events in array")
            else:
                raise ValueError("Expected JSON array or CloudTrail format with 'Records' key")
                
        except Exception as e:
            print(f"❌ Failed to load events from file: {e}")
            sys.exit(1)

        success_count = 0
        for i, event in enumerate(events):
            # Wrap event as EventBridge entry
            entry = {
                "Source": event.get("eventSource", event.get("source", "aws.cloudtrail")),
                "DetailType": event.get("eventName", event.get("detail-type", "CloudTrail Event")),
                "Detail": json.dumps(event),
                "EventBusName": "default",
                "Time": event.get("eventTime", event.get("time", datetime.utcnow().isoformat() + "Z")),
            }
            response = events_client.put_events(Entries=[entry])
            if response["FailedEntryCount"] == 0:
                print(f"✅ Injected event {i+1}/{len(events)}: {entry['DetailType']}")
                success_count += 1
            else:
                print(f"❌ Failed to inject event {i+1}: {response['Entries'][0].get('ErrorMessage')}")
        print(f"\n✅ Successfully injected {success_count}/{len(events)} events from file.")
        print(f"\n💡 Check your dashboard at http://localhost:5000 to see the results!")
        print(f"   Events should appear in DynamoDB within 10-30 seconds.\n")
        return

    # Otherwise, inject synthetic events as before
    print(f"\n🚀 Injecting {args.count} synthetic test events via {args.method}...\n")
    success_count = 0
    for i in range(args.count):
        if args.source == "guardduty":
            template = random.choice(GUARDDUTY_TEMPLATES)
            event = create_guardduty_event(template, custom_severity)
        elif args.source == "securityhub":
            template = random.choice(SECURITYHUB_TEMPLATES)
            event = create_securityhub_event(template, custom_severity if custom_severity else None)
        else:
            if random.choice([True, False]):
                template = random.choice(GUARDDUTY_TEMPLATES)
                event = create_guardduty_event(template, custom_severity)
            else:
                template = random.choice(SECURITYHUB_TEMPLATES)
                event = create_securityhub_event(template, custom_severity if custom_severity else None)

        if args.method == "eventbridge":
            success = inject_event_via_eventbridge(event)
        elif args.method == "stepfunctions":
            success = inject_event_via_stepfunctions(event)
        else:
            success = inject_event_via_eventbridge(event) or inject_event_via_stepfunctions(event)

        if success:
            success_count += 1

    print(f"\n✅ Successfully injected {success_count}/{args.count} synthetic events")
    print(f"\n💡 Check your dashboard at http://localhost:5000 to see the results!")
    print(f"   Events should appear in DynamoDB within 10-30 seconds.\n")


if __name__ == "__main__":
    main()
