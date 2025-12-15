"""
Serverless Dashboard API Lambda
Provides REST endpoints for threat dashboard
"""

import json
import boto3
import os
import logging
from decimal import Decimal

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.client('dynamodb')
TABLE_NAME = os.environ.get('TABLE_NAME', 'ai-soc-dev-state')

def calculate_priority_score(threat_score, source, event_type):
    """
    Calculate priority score matching alert-triage logic.
    Removes circular dependency on severity level.
    """
    # Convert threat_score to 0-100 range if it's in decimal format (0-1)
    # If threat_score is already > 1, assume it's already in 0-100 scale
    if threat_score <= 1.0:
        base_score = threat_score * 100
    elif threat_score > 100:
        # Handle case where it was already multiplied by 100
        base_score = threat_score / 100
    else:
        base_score = threat_score
    
    # Source trust multipliers
    source_weights = {
        "aws.guardduty": 1.2,
        "aws.securityhub": 1.15,
        "aws.cloudtrail": 1.0,
        "aws.config": 1.05,
    }
    
    # Critical event types
    critical_events = [
        "GuardDuty Finding",
        "UnauthorizedAccess",
        "Recon",
        "Trojan",
        "Backdoor",
        "Cryptomining",
        "RootCredentials",
        "IAMUser/AnomalousBehavior"
    ]
    
    # Apply source weight
    source_multiplier = source_weights.get(source, 1.0)
    adjusted_score = base_score * source_multiplier
    
    # Boost for critical event types
    if any(keyword in event_type for keyword in critical_events):
        adjusted_score *= 1.25
    
    return min(100, max(0, adjusted_score))

def get_priority_level(score):
    """Convert priority score to priority level (matching alert-triage logic)"""
    if score >= 90:
        return "CRITICAL"
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"

class DecimalEncoder(json.JSONEncoder):
    """Helper to convert Decimal to int/float for JSON"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

def deserialize_dynamodb_item(item):
    """Convert DynamoDB item format to regular Python dict"""
    if isinstance(item, dict):
        if 'S' in item:
            return item['S']
        elif 'N' in item:
            return float(item['N'])
        elif 'BOOL' in item:
            return item['BOOL']
        elif 'NULL' in item:
            return None
        elif 'M' in item:
            return {k: deserialize_dynamodb_item(v) for k, v in item['M'].items()}
        elif 'L' in item:
            return [deserialize_dynamodb_item(i) for i in item['L']]
    return item

def cors_headers():
    """CORS headers for browser access"""
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET,OPTIONS'
    }

def response(status_code, body):
    """Standard API response"""
    return {
        'statusCode': status_code,
        'headers': cors_headers(),
        'body': json.dumps(body, cls=DecimalEncoder)
    }

def get_threats():
    """Get all threats from DynamoDB"""
    try:
        threats_by_priority = {'CRITICAL': [], 'HIGH': [], 'MEDIUM': [], 'LOW': [], 'UNKNOWN': []}
        last_evaluated_key = None
        max_items_to_scan = 1000  # Scan enough items to get accurate stats

        # Paginate through results with limit
        items_scanned = 0
        while items_scanned < max_items_to_scan:
            scan_kwargs = {
                'TableName': TABLE_NAME,
                'Limit': min(100, max_items_to_scan - items_scanned)  # Fetch in batches of 100
            }
            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key

            result = dynamodb.scan(**scan_kwargs)

            for item in result.get('Items', []):
                deserialized_item = {k: deserialize_dynamodb_item(v) for k, v in item.items()}
                ml_prediction = deserialized_item.get('ml_prediction', {})
                threat_score = float(ml_prediction.get('threat_score', 0))
                prediction_label = ml_prediction.get('prediction_label')
                model_version = ml_prediction.get('model_version')
                evaluated_at = ml_prediction.get('evaluated_at')
                raw_event = deserialized_item.get('raw_event', {})
                severity = deserialized_item.get('severity', 'UNKNOWN')
                source = deserialized_item.get('source', 'unknown')
                event_type = deserialized_item.get('event_type', 'Unknown')
                
                # Use stored priority_level from triage if available, otherwise calculate
                stored_priority = deserialized_item.get('triage', {}).get('priority_level') if isinstance(deserialized_item.get('triage'), dict) else None
                stored_priority_score = deserialized_item.get('triage', {}).get('priority_score') if isinstance(deserialized_item.get('triage'), dict) else None
                
                if stored_priority and stored_priority_score:
                    # Use the priority level that was calculated during triage
                    priority_level = stored_priority
                    priority_score = float(stored_priority_score)
                else:
                    # Fallback: calculate priority score using the same logic as alert-triage
                    priority_score = calculate_priority_score(threat_score, source, event_type)
                    priority_level = get_priority_level(priority_score)

                # Normalize threat_score for display (ensure it's in 0-100 range)
                display_threat_score = threat_score if threat_score > 1.0 else threat_score * 100

                threat = {
                    'alert_id': deserialized_item.get('alert_id', 'N/A'),
                    'timestamp': deserialized_item.get('timestamp', 'N/A'),
                    'severity': severity,
                    'priority_score': priority_score,
                    'priority_level': priority_level,
                    'threat_score': display_threat_score,
                    'event_type': event_type,
                    'source': source,
                    'raw_event': raw_event,
                    'ml_prediction': {
                        'prediction_label': prediction_label,
                        'model_version': model_version,
                        'evaluated_at': evaluated_at,
                        'threat_score': display_threat_score
                    }
                }
                # Ensure priority_level exists in dictionary
                if priority_level not in threats_by_priority:
                    threats_by_priority['UNKNOWN'].append(threat)
                else:
                    threats_by_priority[priority_level].append(threat)

            items_scanned += len(result.get('Items', []))
            last_evaluated_key = result.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break

        # For each priority level, sort by priority_score and take top 50
        top_threats = {}
        actual_counts = {}
        total_count = 0
        for priority_level, threat_list in threats_by_priority.items():
            actual_counts[priority_level] = len(threat_list)  # Store actual count before limiting
            sorted_threats = sorted(threat_list, key=lambda x: x['priority_score'], reverse=True)
            top_threats[priority_level] = sorted_threats[:50]
            total_count += actual_counts[priority_level]  # Use actual count, not limited count

        return response(200, {
            'success': True,
            'count': total_count,
            'counts_by_priority': actual_counts,  # Send actual counts to frontend
            'threats': top_threats
        })
    except Exception as e:
        logger.error(f"Error in get_threats: {str(e)}", exc_info=True)
        return response(500, {
            'success': False,
            'error': str(e)
        })

def get_stats():
    """Get threat statistics - with limit to prevent timeout"""
    try:
        items = []
        last_evaluated_key = None
        max_items_to_scan = 1000  # Scan same amount as get_threats for consistency
        
        # Paginate through results with limit
        items_scanned = 0
        while items_scanned < max_items_to_scan:
            scan_kwargs = {
                'TableName': TABLE_NAME,
                'Limit': min(100, max_items_to_scan - items_scanned)
            }
            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
            
            result = dynamodb.scan(**scan_kwargs)
            items.extend(result.get('Items', []))
            
            items_scanned += len(result.get('Items', []))
            last_evaluated_key = result.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
        
        total = len(items)
        by_severity = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        high_threat = 0
        auto_remediated = 0
        
        for item in items:
            deserialized_item = {k: deserialize_dynamodb_item(v) for k, v in item.items()}
            
            # Use stored priority_level from triage if available, otherwise calculate
            stored_priority = deserialized_item.get('triage', {}).get('priority_level') if isinstance(deserialized_item.get('triage'), dict) else None
            stored_priority_score = deserialized_item.get('triage', {}).get('priority_score') if isinstance(deserialized_item.get('triage'), dict) else None
            
            if stored_priority and stored_priority_score:
                # Use the priority level that was calculated during triage
                priority_level = stored_priority
                priority_score = float(stored_priority_score)
            else:
                # Fallback: Calculate priority_level the same way as in get_threats()
                ml_prediction = deserialized_item.get('ml_prediction', {})
                threat_score = float(ml_prediction.get('threat_score', 0))
                source = deserialized_item.get('source', 'unknown')
                event_type = deserialized_item.get('event_type', 'Unknown')
                
                priority_score = calculate_priority_score(threat_score, source, event_type)
                priority_level = get_priority_level(priority_score)
            
            # Debug: Log first few samples to understand the values
            if items.index(item) < 3:
                logger.info(f"DEBUG Stats - priority_score: {priority_score}, priority_level: {priority_level}, stored: {stored_priority}")
            
            # Count by priority_level instead of severity
            if priority_level in by_severity:
                by_severity[priority_level] += 1
            
            # Count high threat scores
            ml_prediction = deserialized_item.get('ml_prediction', {})
            threat_score = float(ml_prediction.get('threat_score', 0))
            if threat_score > 0.7:
                high_threat += 1
            
            # Count auto-remediated (you can adjust this logic based on your data)
            if deserialized_item.get('remediation_status') == 'auto_remediated':
                auto_remediated += 1
        
        return response(200, {
            'success': True,
            'stats': {
                'total_threats': total,
                'by_severity': by_severity,
                'high_threat_score': high_threat,
                'auto_remediated': auto_remediated
            }
        })
    
    except Exception as e:
        return response(500, {
            'success': False,
            'error': str(e)
        })

def handler(event, context):
    """Lambda handler - routes requests to appropriate function"""
    
    # API Gateway HTTP API uses different event structure
    # Get path from rawPath for HTTP API v2.0
    path = event.get('rawPath', event.get('path', '/'))
    method = event.get('requestContext', {}).get('http', {}).get('method', event.get('httpMethod', 'GET'))
    
    # Handle OPTIONS for CORS preflight
    if method == 'OPTIONS':
        return response(200, {'message': 'OK'})
    
    # Route based on path
    if '/threats' in path:
        return get_threats()
    elif '/stats' in path:
        return get_stats()
    else:
        return response(404, {
            'success': False,
            'error': f'Path not found: {path}',
            'event_keys': list(event.keys())  # Debug info
        })
