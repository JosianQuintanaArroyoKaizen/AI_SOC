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
        response = dynamodb.scan(
            TableName=DYNAMODB_TABLE,
            Limit=50
        )
        
        threats = []
        for item in response.get('Items', []):
            # Parse the event_data JSON string
            event_data_str = item.get('event_data', {}).get('S', '{}')
            try:
                event_data = json.loads(event_data_str)
            except json.JSONDecodeError:
                event_data = {}
            
            threat = {
                'alert_id': item.get('alert_id', {}).get('S', 'N/A'),
                'timestamp': item.get('timestamp', {}).get('S', 'N/A'),
                'severity': item.get('severity', {}).get('S', event_data.get('severity', 'UNKNOWN')),
                'priority_score': int(item.get('priority_score', {}).get('N', 0)),
                'threat_score': int(item.get('threat_score', {}).get('N', 0)),
                'event_type': event_data.get('event_type', 'Unknown'),
                'source': event_data.get('source', 'Unknown'),
                'triage': event_data.get('triage', {}),
                'bedrock_analysis': event_data.get('bedrock_analysis', {}),
                'remediation_result': event_data.get('remediation_result', {}),
            }
            threats.append(threat)
        
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
        response = dynamodb.scan(TableName=DYNAMODB_TABLE)
        items = response.get('Items', [])
        
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
        
        return jsonify({
            'success': True,
            'stats': {
                'total_threats': total,
                'by_severity': by_severity,
                'auto_remediated': auto_remediated,
                'human_review_required': human_review
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
