import json
import logging
import os
import base64
from datetime import datetime
from decimal import Decimal

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

runtime = boto3.client("sagemaker-runtime")
dynamodb = boto3.resource("dynamodb")
ENDPOINT_NAME = os.environ["SAGEMAKER_ENDPOINT"]
STATE_TABLE_NAME = os.environ.get("STATE_TABLE_NAME", "ai-soc-dev-state")
table = dynamodb.Table(STATE_TABLE_NAME)


def handler(event, context):
    """Process Kinesis records, run ML inference, and write to DynamoDB."""
    logger.info(f"Processing {len(event.get('Records', []))} records")
    
    for record in event.get("Records", []):
        try:
            # Decode Kinesis data
            payload = json.loads(base64.b64decode(record["kinesis"]["data"]))
            event_id = payload.get("event_id", "unknown")
            
            logger.info(f"Processing event: {event_id}")
            
            # Extract features and run ML inference
            features = extract_features(payload)
            logger.info(f"Extracted {len(features)} features for event {event_id}")
            
            # Call SageMaker endpoint
            ml_payload = {"features": features}
            response = runtime.invoke_endpoint(
                EndpointName=ENDPOINT_NAME,
                ContentType="application/json",
                Body=json.dumps(ml_payload),
            )
            
            result = json.loads(response["Body"].read().decode())
            threat_score = Decimal(str(result.get("confidence", 1.0)))
            prediction_label = result.get("prediction", "benign")
            
            logger.info(f"ML Result for {event_id}: {prediction_label} (confidence: {threat_score})")
            
            # Write to DynamoDB (convert floats to Decimal for DynamoDB compatibility)
            item = {
                "alert_id": event_id,  # Use alert_id to match DynamoDB schema
                "timestamp": payload.get("timestamp", datetime.utcnow().isoformat()),
                "source": payload.get("source", "unknown"),
                "event_type": payload.get("event_type", "unknown"),
                "severity": payload.get("severity", "UNKNOWN"),
                "raw_event": payload.get("raw_event", {}),
                "ml_prediction": {
                    "threat_score": threat_score,
                    "prediction_label": prediction_label,
                    "model_version": result.get("model_version", "cloudtrail-1.0"),
                    "evaluated_at": datetime.utcnow().isoformat(),
                },
                "processed_at": datetime.utcnow().isoformat(),
            }
            
            table.put_item(Item=item)
            logger.info(f"Successfully wrote event {event_id} to DynamoDB")
            
        except Exception as exc:
            logger.error(f"Error processing record: {exc}", exc_info=True)
            # Continue processing other records
            continue
    
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Processing complete"})
    }


def extract_features(event):
    """Map raw event payload into the 18 CloudTrail-specific features.
    
    Features match those used in training:
    - has_error, is_root, is_iam_user, is_assumed_role
    - is_read, is_write, is_delete
    - hour_of_day, day_of_week, is_weekend
    - is_iam, is_ec2, is_s3, is_lambda, is_kms
    - is_internal_ip, is_aws_service, request_param_count
    """
    raw_event = event.get("raw_event", {})
    
    # Extract CloudTrail-specific fields
    event_name = raw_event.get("eventName", "")
    user_identity = raw_event.get("userIdentity", {})
    source_ip = raw_event.get("sourceIPAddress", "")
    event_time = raw_event.get("eventTime", event.get("timestamp", datetime.utcnow().isoformat()))
    error_code = raw_event.get("errorCode")
    event_source = raw_event.get("eventSource", "")
    request_params = raw_event.get("requestParameters", {})
    
    features = []
    
    # 1. has_error
    features.append(1 if error_code else 0)
    
    # 2-4. User type
    user_type = user_identity.get("type", "Unknown")
    features.append(1 if user_type == "Root" else 0)  # is_root
    features.append(1 if user_type == "IAMUser" else 0)  # is_iam_user
    features.append(1 if user_type == "AssumedRole" else 0)  # is_assumed_role
    
    # 5-7. Event category
    features.append(1 if any(event_name.startswith(p) for p in ['Get', 'List', 'Describe']) else 0)  # is_read
    features.append(1 if any(event_name.startswith(p) for p in ['Put', 'Create', 'Update', 'Modify']) else 0)  # is_write
    features.append(1 if any(event_name.startswith(p) for p in ['Delete', 'Remove', 'Terminate']) else 0)  # is_delete
    
    # 8-10. Time features
    try:
        event_dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
        features.append(event_dt.hour)  # hour_of_day
        features.append(event_dt.weekday())  # day_of_week (0=Monday)
        features.append(1 if event_dt.weekday() >= 5 else 0)  # is_weekend
    except:
        features.append(12)  # default hour
        features.append(2)  # default day (Tuesday)
        features.append(0)  # not weekend
    
    # 11-15. Service flags
    service = event_source.replace('.amazonaws.com', '')
    features.append(1 if service == 'iam' else 0)  # is_iam
    features.append(1 if service == 'ec2' else 0)  # is_ec2
    features.append(1 if service == 's3' else 0)  # is_s3
    features.append(1 if service == 'lambda' else 0)  # is_lambda
    features.append(1 if service == 'kms' else 0)  # is_kms
    
    # 16-17. IP characteristics
    features.append(1 if source_ip.startswith(('10.', '172.', '192.168.')) else 0)  # is_internal_ip
    features.append(1 if '.amazonaws.com' in source_ip else 0)  # is_aws_service
    
    # 18. Request complexity
    features.append(len(request_params) if request_params else 0)  # request_param_count
    
    return features


def get_hour_of_day(timestamp):
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return dt.hour
