#!/usr/bin/env python3
"""
Complete workflow: Train CloudTrail model and test on hold-out set
No external dependencies needed - uses existing infrastructure
"""

import json
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run shell command and handle errors"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"\n❌ Failed: {description}")
        return False
    print(f"\n✅ Completed: {description}")
    return True

def main():
    print("🤖 CloudTrail Model Training & Testing Pipeline")
    print("="*60)
    
    # Check if we have the split data
    train_file = Path("datasets/aws_samples/train.json")
    test_file = Path("datasets/aws_samples/test.json")
    
    if not train_file.exists() or not test_file.exists():
        print("❌ Training/test files not found!")
        print(f"   Expected: {train_file} and {test_file}")
        return 1
    
    # Load and show stats
    with open(train_file) as f:
        train_data = json.load(f)
    with open(test_file) as f:
        test_data = json.load(f)
    
    print(f"\n📊 Dataset Statistics:")
    print(f"   Training: {len(train_data):,} events")
    print(f"   Testing:  {len(test_data):,} events")
    
    # Count severity distribution in training set
    severity_counts = {}
    for event in train_data:
        sev = event.get("llm_severity", "UNKNOWN")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    print(f"\n   Training Severity Distribution:")
    for sev, count in sorted(severity_counts.items()):
        pct = (count / len(train_data)) * 100
        print(f"      {sev:10s}: {count:5d} ({pct:5.1f}%)")
    
    # Step 1: Train the model locally (it will use llm_severity labels)
    print(f"\n📍 Step 1/3: Training Model")
    success = run_command(
        ["python3", "ml_training/train_cloudtrail_model.py", 
         "--input", str(train_file),
         "--output", "models/cloudtrail_v2.pkl"],
        "Train CloudTrail model with LLM-labeled data"
    )
    
    if not success:
        print("\n⚠️  Training failed - trying with Docker...")
        success = run_command(
            ["docker", "run", "--rm", 
             "-v", f"{Path.cwd()}/datasets:/datasets",
             "-v", f"{Path.cwd()}/models:/models",
             "-v", f"{Path.cwd()}/ml_training:/ml_training",
             "python:3.11-slim",
             "bash", "-c",
             "pip install -q numpy pandas scikit-learn && python3 /ml_training/train_cloudtrail_model.py --input /datasets/aws_samples/train.json --output /models/cloudtrail_v2.pkl"],
            "Train with Docker container"
        )
        
        if not success:
            print("\n❌ Could not train model")
            print("💡 Manual option: Install dependencies and run:")
            print(f"   pip install numpy pandas scikit-learn")
            print(f"   python3 ml_training/train_cloudtrail_model.py --input {train_file} --output models/cloudtrail_v2.pkl")
            return 1
    
    # Step 2: Test the model (send test events through the pipeline)
    print(f"\n📍 Step 2/3: Testing Model on Hold-out Set")
    print(f"   Sending {len(test_data)} test events to Lambda pipeline...")
    
    # Create a script to send test events
    test_script = Path("scripts/send_test_events.py")
    with open(test_script, "w") as f:
        f.write('''#!/usr/bin/env python3
import json
import boto3
import sys
from pathlib import Path

eventbridge = boto3.client("events", region_name="eu-central-1")

# Load test data
with open("datasets/aws_samples/test.json") as f:
    test_events = json.load(f)

print(f"Sending {len(test_events)} test events to EventBridge...")
sent = 0
failed = 0

for i, event in enumerate(test_events):
    try:
        # Send to EventBridge (will trigger Lambda pipeline)
        response = eventbridge.put_events(
            Entries=[{
                "Source": "aws.cloudtrail",
                "DetailType": "AWS API Call via CloudTrail",
                "Detail": json.dumps(event)
            }]
        )
        if response["FailedEntryCount"] == 0:
            sent += 1
        else:
            failed += 1
        
        if (i + 1) % 100 == 0:
            print(f"  Progress: {i+1}/{len(test_events)} ({sent} sent, {failed} failed)")
    except Exception as e:
        print(f"  Error sending event {i}: {e}")
        failed += 1

print(f"\\n✅ Sent {sent} events successfully")
if failed > 0:
    print(f"⚠️  Failed to send {failed} events")
''')
    
    success = run_command(
        ["python3", str(test_script)],
        "Send test events through pipeline"
    )
    
    # Step 3: Check results in DynamoDB
    print(f"\n📍 Step 3/3: Analyzing Results")
    print(f"   Waiting 30 seconds for pipeline processing...")
    import time
    time.sleep(30)
    
    run_command(
        ["aws", "dynamodb", "scan",
         "--table-name", "ai-soc-dev-state",
         "--region", "eu-central-1",
         "--select", "COUNT",
         "--output", "table"],
        "Check processed events in DynamoDB"
    )
    
    print(f"\n🎉 Pipeline Complete!")
    print(f"\n📊 View Results:")
    print(f"   Dashboard: http://ai-soc-dev-dashboard-194561596031.s3-website.eu-central-1.amazonaws.com/")
    print(f"\n📈 Compare severity distribution:")
    print(f"   - Training data was {len(train_data)} events")
    print(f"   - Test data was {len(test_data)} events")
    print(f"   - Check dashboard to see how model classified the test set")

if __name__ == "__main__":
    sys.exit(main())
