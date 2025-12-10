"""
Serverless Dashboard API Lambda
Provides REST endpoints for threat dashboard
"""

import json
import boto3
import os
from decimal import Decimal

dynamodb = boto3.client('dynamodb')
TABLE_NAME = os.environ.get('TABLE_NAME', 'ai-soc-dev-state')

class DecimalEncoder(json.JSONEncoder):
    """Helper to convert Decimal to int/float for JSON"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

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
        threats = []
        last_evaluated_key = None
        
        # Paginate through all results
        while True:
            scan_kwargs = {'TableName': TABLE_NAME}
            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
            
            result = dynamodb.scan(**scan_kwargs)
            
            for item in result.get('Items', []):
                # Extract ml_prediction nested structure
                ml_prediction = item.get('ml_prediction', {}).get('M', {})
                threat_score = float(ml_prediction.get('threat_score', {}).get('N', 0))
                
                # Parse raw_event for additional context if needed
                raw_event_str = item.get('raw_event', {}).get('S', '{}')
                try:
                    raw_event = json.loads(raw_event_str)
                except json.JSONDecodeError:
                    raw_event = {}
                
                # Calculate priority score based on threat score and severity
                severity = item.get('severity', {}).get('S', 'UNKNOWN')
                severity_weights = {'CRITICAL': 100, 'HIGH': 75, 'MEDIUM': 50, 'LOW': 25, 'UNKNOWN': 0}
                priority_score = (threat_score * 100) * 0.6 + severity_weights.get(severity, 0) * 0.4
                
                threat = {
                    'alert_id': item.get('alert_id', {}).get('S', 'N/A'),
                    'timestamp': item.get('timestamp', {}).get('S', 'N/A'),
                    'severity': severity,
                    'priority_score': priority_score,
                    'threat_score': threat_score * 100,  # Convert to 0-100 scale
                    'event_type': item.get('event_type', {}).get('S', 'Unknown'),
                    'source': item.get('source', {}).get('S', 'Unknown'),
                    'raw_event': raw_event,
                }
                threats.append(threat)
            
            # Check if there are more results
            last_evaluated_key = result.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
        
        # Sort by priority (highest first)
        threats.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return response(200, {
            'success': True,
            'count': len(threats),
            'threats': threats
        })
    
    except Exception as e:
        return response(500, {
            'success': False,
            'error': str(e)
        })

def get_stats():
    """Get threat statistics"""
    try:
        items = []
        last_evaluated_key = None
        
        # Paginate through all results
        while True:
            scan_kwargs = {'TableName': TABLE_NAME}
            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
            
            result = dynamodb.scan(**scan_kwargs)
            items.extend(result.get('Items', []))
            
            last_evaluated_key = result.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
        
        total = len(items)
        by_severity = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'UNKNOWN': 0}
        high_threat = 0
        
        for item in items:
            severity = item.get('severity', {}).get('S', 'UNKNOWN')
            by_severity[severity] = by_severity.get(severity, 0) + 1
            
            # Count high threat scores
            ml_prediction = item.get('ml_prediction', {}).get('M', {})
            threat_score = float(ml_prediction.get('threat_score', {}).get('N', 0))
            if threat_score > 0.7:
                high_threat += 1
        
        return response(200, {
            'success': True,
            'stats': {
                'total_threats': total,
                'by_severity': by_severity,
                'high_threat_score': high_threat
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
