"""
Simple Threat Viewer Dashboard
Reads threats from DynamoDB and displays with AI analysis
"""

from flask import Flask, render_template, jsonify
import boto3
from datetime import datetime
import json

app = Flask(__name__)

# AWS Configuration
DYNAMODB_TABLE = 'ai-soc-dev-state'
AWS_REGION = 'eu-central-1'

dynamodb = boto3.client('dynamodb', region_name=AWS_REGION)

@app.route('/')
def index():
    """Main threat dashboard"""
    return render_template('threats.html')

@app.route('/api/threats')
def get_threats():
    """Get all threats from DynamoDB"""
    try:
        threats = []
        last_evaluated_key = None
        
        # Paginate through all results
        while True:
            scan_kwargs = {'TableName': DYNAMODB_TABLE}
            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
            
            response = dynamodb.scan(**scan_kwargs)
            
            for item in response.get('Items', []):
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
            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
        
        # Sort by priority score (highest first)
        threats.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return jsonify({
            'success': True,
            'count': len(threats),
            'threats': threats
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/threat/<alert_id>')
def get_threat_detail(alert_id):
    """Get detailed information for a specific threat"""
    try:
        # Need to scan because we don't have the timestamp
        response = dynamodb.scan(
            TableName=DYNAMODB_TABLE,
            FilterExpression='alert_id = :aid',
            ExpressionAttributeValues={
                ':aid': {'S': alert_id}
            }
        )
        
        if not response.get('Items'):
            return jsonify({'success': False, 'error': 'Threat not found'}), 404
        
        item = response['Items'][0]
        event_data_str = item.get('event_data', {}).get('S', '{}')
        event_data = json.loads(event_data_str)
        
        return jsonify({
            'success': True,
            'threat': {
                'alert_id': item.get('alert_id', {}).get('S'),
                'timestamp': item.get('timestamp', {}).get('S'),
                'full_data': event_data
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get threat statistics"""
    try:
        items = []
        last_evaluated_key = None
        
        # Paginate through all results
        while True:
            scan_kwargs = {'TableName': DYNAMODB_TABLE}
            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
            
            response = dynamodb.scan(**scan_kwargs)
            items.extend(response.get('Items', []))
            
            last_evaluated_key = response.get('LastEvaluatedKey')
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
        
        return jsonify({
            'success': True,
            'stats': {
                'total_threats': total,
                'by_severity': by_severity,
                'high_threat_score': high_threat
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 AI-SOC Threat Viewer starting...")
    print("📊 Dashboard: http://localhost:5000")
    print("📡 API: http://localhost:5000/api/threats")
    print()
    app.run(host='0.0.0.0', port=5000, debug=True)
