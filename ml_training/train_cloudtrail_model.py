#!/usr/bin/env python3
"""
Train an IDS model specifically for AWS CloudTrail events.
Uses heuristic-based labeling to classify events as benign or suspicious.
"""

import json
import pickle
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix


def load_cloudtrail_data(file_path):
    """Load CloudTrail events from JSON file"""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Handle both array format and Records wrapper
    if isinstance(data, list):
        return data
    return data.get('Records', [])


def label_event(event):
    """
    Heuristic-based labeling of CloudTrail events.
    Returns 1 for suspicious, 0 for benign.
    
    Suspicious indicators:
    - Error codes (potential unauthorized access attempts)
    - Root account usage
    - Unusual console logins (especially outside business hours)
    - Destructive operations (Delete*, Terminate*)
    - Security-related changes (IAM, Security Group modifications)
    - Multiple assume role attempts
    """
    event_name = event.get('eventName', '')
    error_code = event.get('errorCode')
    user_identity = event.get('userIdentity', {})
    event_time = event.get('eventTime', '')
    source_ip = event.get('sourceIPAddress', '')
    
    # Suspicious patterns
    suspicious_score = 0
    
    # 1. Error codes indicate potential unauthorized access
    if error_code:
        if error_code in ['UnauthorizedOperation', 'AccessDenied', 'InvalidPermission']:
            suspicious_score += 3
        else:
            suspicious_score += 1
    
    # 2. Root account usage
    if user_identity.get('type') == 'Root':
        suspicious_score += 2
    
    # 3. Destructive operations
    if any(event_name.startswith(prefix) for prefix in ['Delete', 'Terminate', 'Remove', 'Detach']):
        suspicious_score += 2
    
    # 4. Security-sensitive operations (expanded list for better balance)
    security_events = ['PutUserPolicy', 'AttachUserPolicy', 'CreateAccessKey', 
                      'AuthorizeSecurityGroupIngress', 'ModifyDBInstance',
                      'PutBucketPolicy', 'CreateFunction', 'UpdateFunctionCode',
                      'UpdateEnvironmentSettings', 'UpdateUserSettings',
                      'UpdateMembershipSettings', 'ModifyInstanceAttribute']
    if event_name in security_events:
        suspicious_score += 1
    
    # 5. High-frequency update operations (potential reconnaissance)
    if event_name.startswith('Update') and event_name not in ['UpdateItem']:
        suspicious_score += 0.5
    
    # 5. Off-hours activity (basic heuristic - can be improved)
    try:
        event_dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
        hour = event_dt.hour
        # Suspicious if between midnight and 5 AM UTC
        if 0 <= hour < 5:
            suspicious_score += 1
    except:
        pass
    
    # 6. Console login from unusual source
    if event_name == 'ConsoleLogin':
        # Any console login gets slight suspicion boost (can be refined)
        suspicious_score += 1
    
    # 7. AssumeRole operations (lateral movement indicator)
    if 'AssumeRole' in event_name:
        suspicious_score += 0.5
    
    # Label as suspicious if score >= 1.5 (lowered threshold for more balanced dataset)
    return 1 if suspicious_score >= 1.5 else 0


def extract_features(event):
    """Extract numerical features from CloudTrail event"""
    event_name = event.get('eventName', '')
    user_identity = event.get('userIdentity', {})
    source_ip = event.get('sourceIPAddress', '')
    event_time = event.get('eventTime', '')
    error_code = event.get('errorCode')
    
    features = {}
    
    # 1. Has error (binary)
    features['has_error'] = 1 if error_code else 0
    
    # 2. User type encoding
    user_type = user_identity.get('type', 'Unknown')
    features['is_root'] = 1 if user_type == 'Root' else 0
    features['is_iam_user'] = 1 if user_type == 'IAMUser' else 0
    features['is_assumed_role'] = 1 if user_type == 'AssumedRole' else 0
    
    # 3. Event category flags
    features['is_read'] = 1 if any(event_name.startswith(p) for p in ['Get', 'List', 'Describe']) else 0
    features['is_write'] = 1 if any(event_name.startswith(p) for p in ['Put', 'Create', 'Update', 'Modify']) else 0
    features['is_delete'] = 1 if any(event_name.startswith(p) for p in ['Delete', 'Remove', 'Terminate']) else 0
    
    # 4. Time-based features
    try:
        event_dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
        features['hour_of_day'] = event_dt.hour
        features['day_of_week'] = event_dt.weekday()  # 0=Monday, 6=Sunday
        features['is_weekend'] = 1 if event_dt.weekday() >= 5 else 0
    except:
        features['hour_of_day'] = 12
        features['day_of_week'] = 2
        features['is_weekend'] = 0
    
    # 5. Service encoding (top services)
    service = event.get('eventSource', '').replace('.amazonaws.com', '')
    features['is_iam'] = 1 if service == 'iam' else 0
    features['is_ec2'] = 1 if service == 'ec2' else 0
    features['is_s3'] = 1 if service == 's3' else 0
    features['is_lambda'] = 1 if service == 'lambda' else 0
    features['is_kms'] = 1 if service == 'kms' else 0
    
    # 6. Source IP characteristics (basic heuristic)
    features['is_internal_ip'] = 1 if source_ip.startswith(('10.', '172.', '192.168.')) else 0
    features['is_aws_service'] = 1 if '.amazonaws.com' in source_ip else 0
    
    # 7. Request parameters complexity
    request_params = event.get('requestParameters', {})
    features['request_param_count'] = len(request_params) if request_params else 0
    
    return features


def train_cloudtrail_model(data_file, output_dir='models'):
    """Train Random Forest model on CloudTrail data"""
    print("=" * 80)
    print("CLOUDTRAIL IDS MODEL TRAINING")
    print("=" * 80)
    print()
    
    # Load data
    print(f"Loading data from {data_file}...")
    events = load_cloudtrail_data(data_file)
    print(f"Loaded {len(events)} CloudTrail events")
    print()
    
    # Extract features and labels
    print("Extracting features and labels...")
    features_list = []
    labels = []
    use_llm_labels = 'llm_severity' in events[0] if events else False
    
    if use_llm_labels:
        print("Using LLM-provided severity labels")
    else:
        print("Using heuristic-based labels")
    
    for event in events:
        try:
            features = extract_features(event)
            
            # Use LLM labels if available, otherwise use heuristic
            if use_llm_labels and 'llm_severity' in event:
                llm_severity = event['llm_severity'].upper()
                # Map severity to binary: LOW=0, MEDIUM/HIGH/CRITICAL=1
                label = 1 if llm_severity in ['MEDIUM', 'HIGH', 'CRITICAL'] else 0
            else:
                label = label_event(event)
            
            features_list.append(features)
            labels.append(label)
        except Exception as e:
            print(f"Warning: Failed to process event: {e}")
            continue
    
    # Convert to DataFrame
    df = pd.DataFrame(features_list)
    labels = np.array(labels)
    
    print(f"Extracted {len(df)} samples with {len(df.columns)} features")
    print(f"Features: {list(df.columns)}")
    print()
    
    # Class distribution
    label_counts = Counter(labels)
    print("Class distribution:")
    print(f"  Benign (0): {label_counts[0]} ({label_counts[0]/len(labels)*100:.1f}%)")
    print(f"  Suspicious (1): {label_counts[1]} ({label_counts[1]/len(labels)*100:.1f}%)")
    print()
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        df, labels, test_size=0.2, random_state=42, stratify=labels
    )
    
    print(f"Training set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    print()
    
    # Scale features
    print("Scaling features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train model
    print("Training Random Forest model...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        class_weight='balanced',
        n_jobs=-1
    )
    model.fit(X_train_scaled, y_train)
    print("Training complete!")
    print()
    
    # Evaluate
    print("Evaluating model...")
    y_pred = model.predict(X_test_scaled)
    
    print("\nClassification Report:")
    # Use labels parameter to handle imbalanced classes
    unique_labels = sorted(list(set(y_test) | set(y_pred)))
    target_names = ['Benign', 'Suspicious'] if len(unique_labels) == 2 else ['Benign']
    print(classification_report(y_test, y_pred, labels=unique_labels, target_names=target_names[:len(unique_labels)], zero_division=0))
    
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred, labels=unique_labels)
    if len(unique_labels) == 2:
        print(f"                Predicted")
        print(f"                Benign  Suspicious")
        print(f"Actual Benign      {cm[0][0]:4d}      {cm[0][1]:4d}")
        print(f"       Suspicious  {cm[1][0]:4d}      {cm[1][1]:4d}")
    else:
        print(f"All samples predicted as: {target_names[0]}")
    print()
    
    # Feature importance
    print("Top 10 Most Important Features:")
    feature_importance = pd.DataFrame({
        'feature': df.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for idx, row in feature_importance.head(10).iterrows():
        print(f"  {row['feature']:25s}: {row['importance']:.4f}")
    print()
    
    # Save model artifacts
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print(f"Saving model artifacts to {output_path}/...")
    
    # Save model
    model_file = output_path / 'cloudtrail_random_forest.pkl'
    with open(model_file, 'wb') as f:
        pickle.dump(model, f)
    print(f"  ✓ Model saved: {model_file}")
    
    # Save scaler
    scaler_file = output_path / 'cloudtrail_scaler.pkl'
    with open(scaler_file, 'wb') as f:
        pickle.dump(scaler, f)
    print(f"  ✓ Scaler saved: {scaler_file}")
    
    # Save feature names
    feature_names_file = output_path / 'cloudtrail_feature_names.pkl'
    with open(feature_names_file, 'wb') as f:
        pickle.dump(list(df.columns), f)
    print(f"  ✓ Feature names saved: {feature_names_file}")
    
    # Save label encoder (simple binary: 0=benign, 1=suspicious)
    label_encoder_file = output_path / 'cloudtrail_label_encoder.pkl'
    le = LabelEncoder()
    le.fit(['benign', 'suspicious'])
    with open(label_encoder_file, 'wb') as f:
        pickle.dump(le, f)
    print(f"  ✓ Label encoder saved: {label_encoder_file}")
    
    print()
    print("=" * 80)
    print("TRAINING COMPLETE!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Deploy model to SageMaker:")
    print("   python3 ml_training/deploy_to_sagemaker.py --model cloudtrail_random_forest --no-docker")
    print()
    print("2. Test the model locally:")
    print("   python3 ml_training/test_cloudtrail_inference.py")
    
    return model, scaler, df.columns


if __name__ == '__main__':
    # Use train.json if available (LLM-labeled), otherwise shared_services.json
    train_file = 'datasets/aws_samples/train.json'
    data_file = train_file if Path(train_file).exists() else 'datasets/aws_samples/shared_services.json'
    
    if not Path(data_file).exists():
        print(f"Error: Data file not found: {data_file}")
        sys.exit(1)
    
    print(f"Using data file: {data_file}\n")
    train_cloudtrail_model(data_file)
