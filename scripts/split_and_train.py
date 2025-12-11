#!/usr/bin/env python3
"""
Split labeled dataset and train CloudTrail model with LLM severity labels
"""

import json
import random
from pathlib import Path

# Configuration
INPUT_FILE = "datasets/aws_samples/shared_services_labeled.json"
TRAIN_FILE = "datasets/aws_samples/train_set.json"
TEST_FILE = "datasets/aws_samples/test_set.json"
TRAIN_RATIO = 0.8

def main():
    print("🔀 Splitting Labeled Dataset")
    print("=" * 60)
    
    # Load labeled data
    print(f"\n📂 Loading: {INPUT_FILE}")
    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)
    
    # Handle Records wrapper
    if isinstance(data, dict) and 'Records' in data:
        events = data['Records']
    elif isinstance(data, list):
        events = data
    else:
        raise ValueError("Unexpected format")
    
    total = len(events)
    print(f"✅ Loaded {total:,} labeled events")
    
    # Show distribution
    severity_counts = {}
    for event in events:
        sev = event.get('llm_severity', 'UNKNOWN')
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    print("\n📊 Severity Distribution:")
    for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        count = severity_counts.get(sev, 0)
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {sev:12} {count:5} ({pct:5.1f}%)")
    
    # Shuffle and split
    random.seed(42)  # Reproducible split
    random.shuffle(events)
    
    split_idx = int(total * TRAIN_RATIO)
    train_set = events[:split_idx]
    test_set = events[split_idx:]
    
    print(f"\n✂️  Split:")
    print(f"  Training: {len(train_set):,} events ({len(train_set)/total*100:.1f}%)")
    print(f"  Test:     {len(test_set):,} events ({len(test_set)/total*100:.1f}%)")
    
    # Save training set
    print(f"\n💾 Saving training set: {TRAIN_FILE}")
    with open(TRAIN_FILE, 'w') as f:
        json.dump({"Records": train_set}, f, indent=2)
    
    # Save test set
    print(f"💾 Saving test set: {TEST_FILE}")
    with open(TEST_FILE, 'w') as f:
        json.dump({"Records": test_set}, f, indent=2)
    
    print("\n✅ Data split complete!")
    print(f"\n📝 Next steps:")
    print(f"  1. Train model: cd ml_training && python train_cloudtrail_model.py")
    print(f"  2. Process test set through pipeline")

if __name__ == "__main__":
    main()
