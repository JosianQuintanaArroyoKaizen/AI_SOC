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
        result = dynamodb.scan(
            TableName=TABLE_NAME,
            Limit=50
        )
        
        threats = []
        for item in result.get('Items', []):
            # Parse event_data JSON
            event_data_str = item.get('event_data', {}).get('S', '{}')
            try:
                event_data = json.loads(event_data_str)
            except json.JSONDecodeError:
                event_data = {}
            
            threat = {
                'alert_id': item.get('alert_id', {}).get('S', 'N/A'),
                'timestamp': item.get('timestamp', {}).get('S', 'N/A'),
                'severity': item.get('severity', {}).get('S', event_data.get('severity', 'UNKNOWN')),
                'priority_score': float(item.get('priority_score', {}).get('N', 0)),
                'threat_score': float(item.get('threat_score', {}).get('N', 0)),
                'event_type': event_data.get('event_type', 'Unknown'),
                'source': event_data.get('source', 'Unknown'),
                'triage': event_data.get('triage', {}),
                'bedrock_analysis': event_data.get('bedrock_analysis', {}),
            }
            threats.append(threat)
        
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
        result = dynamodb.scan(TableName=TABLE_NAME)
        items = result.get('Items', [])
        
        total = len(items)
        by_severity = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'UNKNOWN': 0}
        auto_remediated = 0
        human_review = 0
        
        for item in items:
            event_data_str = item.get('event_data', {}).get('S', '{}')
            try:
                event_data = json.loads(event_data_str)
                severity = event_data.get('severity', 'UNKNOWN')
                by_severity[severity] = by_severity.get(severity, 0) + 1
                
                triage = event_data.get('triage', {})
                if triage.get('auto_remediate'):
                    auto_remediated += 1
                if triage.get('requires_human_review'):
                    human_review += 1
            except:
                by_severity['UNKNOWN'] += 1
        
        return response(200, {
            'success': True,
            'stats': {
                'total_threats': total,
                'by_severity': by_severity,
                'auto_remediated': auto_remediated,
                'human_review_required': human_review
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
