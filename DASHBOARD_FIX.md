# Dashboard Fix Summary

## Issue
The S3-hosted dashboard was showing a 500 error with the message:
```
Error: invalid literal for int() with base 10: '56.30267293627242'
```

## Root Cause
The Lambda function (`dashboard-api`) was trying to convert DynamoDB numeric values to integers using `int()`, but the Step Functions workflow was storing **float values** for priority scores and threat scores (e.g., `56.30267293627242`).

## Why Float Values?
The Alert Triage Lambda calculates priority scores using this formula:
```python
base_score = (threat_score * 0.6) + severity_weights.get(severity, 10)
adjusted_score = base_score * source_weights.get(source, 1.0)
```

This creates decimal values like `56.30267293627242`, which are valid precision scores.

## Solution
Changed the data type conversion from `int()` to `float()` in two files:

### 1. Lambda API (for S3 dashboard)
**File:** `lambda/dashboard-api/index.py`

**Before:**
```python
'priority_score': int(item.get('priority_score', {}).get('N', 0)),
'threat_score': int(item.get('threat_score', {}).get('N', 0)),
```

**After:**
```python
'priority_score': float(item.get('priority_score', {}).get('N', 0)),
'threat_score': float(item.get('threat_score', {}).get('N', 0)),
```

### 2. Local Dashboard (for local testing)
**File:** `dashboard/threat_viewer.py` - Same fix applied

## Deployment
The Lambda function was updated and deployed:
```bash
cd lambda/dashboard-api
zip lambda.zip index.py
aws lambda update-function-code \
  --function-name ai-soc-dev-dashboard-api \
  --zip-file fileb://lambda.zip \
  --region eu-central-1
```

## Testing
After the fix, the API now returns proper JSON:
```json
{
    "alert_id": "test-sh-59354",
    "priority_score": 73.21,
    "threat_score": 94.26,
    ...
}
```

## Dashboard URLs
- **S3 Hosted:** http://ai-soc-dev-dashboard-194561596031.s3-website.eu-central-1.amazonaws.com/
- **API Endpoint:** https://rstevhgym8.execute-api.eu-central-1.amazonaws.com/threats

## Status
✅ **FIXED** - Dashboard should now display all threats correctly with accurate decimal precision scores.

Refresh your browser to see the updated data!
