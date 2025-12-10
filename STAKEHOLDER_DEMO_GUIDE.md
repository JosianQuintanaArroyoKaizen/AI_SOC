# AI-SOC Stakeholder Demo Guide

## Preparing Your Demo

### Before the Meeting

#### 1. Generate Realistic Test Data (15 minutes before)

```bash
# Activate your environment
cd /home/jquintana-arroyo/git/AI_SOC
source .venv/bin/activate

# Generate a variety of realistic threats
python3 scripts/inject_test_events.py --count 25

# Wait 30 seconds for processing
sleep 30

# Verify events are visible
curl -s "https://rstevhgym8.execute-api.eu-central-1.amazonaws.com/threats" | python3 -m json.tool | head -50
```

#### 2. Prepare Your Dashboard
**URL:** http://ai-soc-dev-dashboard-194561596031.s3-website.eu-central-1.amazonaws.com/

Open in browser and verify:
- ✅ Threats are loading
- ✅ Severity badges are showing (CRITICAL, HIGH, MEDIUM, LOW)
- ✅ Threat scores are visible
- ✅ AI analysis details are present

#### 3. Have AWS Console Ready
Open these in separate tabs:
- Step Functions: https://eu-central-1.console.aws.amazon.com/states/home?region=eu-central-1#/statemachines
- DynamoDB: https://eu-central-1.console.aws.amazon.com/dynamodbv2/home?region=eu-central-1#table?name=ai-soc-dev-state
- CloudWatch Logs: https://eu-central-1.console.aws.amazon.com/cloudwatch/home?region=eu-central-1#logsV2:log-groups

---

## Demo Script (15-20 minutes)

### Introduction (2 minutes)

**"I'd like to show you our AI-powered Security Operations Center that I've built. This system autonomously monitors our AWS environment, analyzes security threats using AI, and can automatically respond to incidents."**

Key points to mention:
- Fully serverless (scales automatically, pay-per-use)
- Real-time threat detection and response
- AI-powered analysis using Amazon Bedrock
- Currently deployed in dev environment, ready for production

---

### Part 1: The Dashboard (5 minutes)

**Show:** http://ai-soc-dev-dashboard-194561596031.s3-website.eu-central-1.amazonaws.com/

**Talk track:**
1. **"This is our centralized threat dashboard hosted on S3 - accessible to the security team 24/7."**

2. **"Each row represents a security event detected by AWS GuardDuty or Security Hub. Let me walk you through what we're seeing:"**

3. **Point to a CRITICAL alert:**
   - "Here's a critical threat - notice the red badge"
   - "Priority score of 90+ means automatic remediation was triggered"
   - "Threat score of 85+ indicates our ML model detected suspicious patterns"

4. **Click on an alert to expand details:**
   - "The AI analysis (powered by Claude) provides context"
   - "Risk assessment, attack vector analysis, and recommended actions"
   - "Remediation actions taken automatically"

5. **"The color coding helps us triage:"**
   - Red = CRITICAL (immediate action taken)
   - Orange = HIGH (security team notified)
   - Yellow = MEDIUM (logged and monitored)
   - Blue = LOW (archived for compliance)

---

### Part 2: The Architecture (3 minutes)

**Show:** Architecture diagram or explain with console tabs

**Talk track:**
**"Let me show you how this works behind the scenes. The system has 5 main stages:"**

1. **Data Collection** *(Show EventBridge Rules)*
   - "We monitor AWS GuardDuty and Security Hub"
   - "These services watch for unauthorized access, malware, misconfigurations"
   - "Events are captured in real-time via EventBridge"

2. **Event Processing** *(Show Kinesis in console)*
   - "Events flow through Kinesis for high-throughput processing"
   - "Can handle thousands of events per minute"

3. **ML Analysis** *(Show Step Functions)*
   - "Each event is analyzed by our ML model"
   - "Threat score from 0-100 based on patterns"
   - "Priority calculation considers severity, source, and context"

4. **AI Deep Analysis** *(Show Bedrock/Claude)*
   - "High-priority threats (>70) get deep AI analysis"
   - "Claude provides human-readable insights"
   - "Recommends specific response actions"

5. **Automated Response** *(Show Remediation Lambda logs)*
   - "Critical threats trigger automatic remediation"
   - "Disables compromised credentials"
   - "Blocks malicious IPs"
   - "Notifies security team"

**"All of this happens in seconds - from detection to response."**

---

### Part 3: Live Workflow (5 minutes)

**Show:** Step Functions execution in AWS Console

**Talk track:**
1. **Navigate to Step Functions console**
   - "Here's a live execution of our security workflow"
   - "Each green box is a successful step"

2. **Click on a recent execution**
   - "This shows the journey of a security event"
   - "Started with Alert Triage"
   - "Moved to Bedrock Analysis because priority was high"
   - "Attempted Remediation"
   - "Saved to DynamoDB for the dashboard"

3. **Show execution time**
   - "Total processing time: typically 5-15 seconds"
   - "From event detection to remediation"

4. **Show input/output of a step**
   - "Here's the raw event data"
   - "And here's the enriched data with AI analysis"

---

### Part 4: Real-World Value (3 minutes)

**Key benefits to highlight:**

**1. Speed**
- "Traditional SOC: Hours to days for incident response"
- "Our AI-SOC: Seconds to minutes"
- "Critical threats automatically contained"

**2. Cost**
- "Traditional SOC: $200K-500K annually for staff"
- "Our AI-SOC: ~$150-250/month in AWS costs"
- "No 24/7 human monitoring required"

**3. Coverage**
- "Never sleeps - monitors 24/7/365"
- "Analyzes 100% of security events"
- "No alert fatigue - only escalates what matters"

**4. Intelligence**
- "Learns from patterns across all events"
- "AI provides context humans might miss"
- "Consistent analysis - no human error"

**5. Compliance**
- "All events logged to DynamoDB"
- "Audit trail of all decisions and actions"
- "Demonstrates due diligence for auditors"

---

### Part 5: Next Steps (2 minutes)

**Production Deployment Path:**

**Phase 1: Pilot (Current - Dev Account)**
- ✅ Infrastructure deployed and tested
- ✅ Pipeline validated with test events
- ✅ Dashboard functional

**Phase 2: Production Deployment (2-4 weeks)**
- Deploy to production AWS account
- Enable GuardDuty/Security Hub
- Monitor real events for 2 weeks
- Tune thresholds and response actions

**Phase 3: Optimization (Ongoing)**
- Refine ML models based on real data
- Add custom detection rules
- Integrate with existing tools (Slack, PagerDuty)
- Expand to multi-account monitoring

---

## Anticipated Questions & Answers

### Q: "What happens if it makes a wrong decision?"
**A:** "Great question. We have safeguards:
- Only CRITICAL priority (>90) triggers auto-remediation
- All actions are logged and reversible
- Security team is notified for every high-priority event
- We can tune thresholds based on false positive rate
- In production, we'd start with 'notify only' mode before enabling auto-remediation"

### Q: "Can it integrate with our existing tools?"
**A:** "Absolutely. The system uses SNS for notifications, which can route to:
- Email
- Slack
- PagerDuty
- ServiceNow
- Any webhook-based system
We can add custom integrations as needed."

### Q: "What about false positives?"
**A:** "The ML model and AI analysis help reduce false positives significantly. Plus:
- Low priority events are just logged, not acted on
- Security team reviews trends weekly
- We can add exceptions for known good patterns
- The system learns from feedback over time"

### Q: "How much does this cost to run?"
**A:** "In this dev environment: ~$50-100/month
In production with real workload: ~$150-250/month
Compare that to $200K+ annually for traditional SOC staffing.
The infrastructure scales with usage, so costs are proportional to activity."

### Q: "How long to deploy to production?"
**A:** "The infrastructure can be deployed in 2-4 hours.
But I'd recommend:
- Week 1: Deploy infrastructure
- Week 2-3: Monitor in 'observe only' mode
- Week 4: Enable auto-remediation for critical threats
- Ongoing: Tune and optimize

Total time to full production: 4-6 weeks for cautious rollout."

### Q: "What if AWS has an outage?"
**A:** "The system is regional but can be deployed multi-region:
- Core services (Lambda, DynamoDB) have 99.99% SLA
- We can configure cross-region replication
- Events are buffered in Kinesis during brief outages
- Manual fallback to traditional processes if needed"

### Q: "Can you demonstrate a real attack?"
**A:** "What you're seeing are realistic simulations based on actual GuardDuty findings.
To see real events, we need to:
1. Deploy to production account with actual workloads
2. Enable GuardDuty/Security Hub (if not already)
3. Wait for real security events

In typical production environments, you'd see 50-200 events per day.
Common real-world examples: Failed SSH attempts, unusual API calls, credential exposure."

---

## Demo Failure Scenarios & Recovery

### If Dashboard Won't Load
**Fallback:** Use DynamoDB console directly
- Show table with events
- Explain structure
- Use JSON viewer for event details

### If No Events in Dashboard
**Fallback:** Generate events live during demo
```bash
python3 scripts/inject_test_events.py --count 5 --severity CRITICAL
# Wait 30 seconds, refresh dashboard
```

### If API Returns Errors
**Fallback:** Show CloudWatch Logs
- Demonstrate observability
- Show Lambda execution traces
- Explain error handling

---

## Post-Demo Follow-Up Email Template

```
Subject: AI-SOC Demo Follow-Up - Next Steps

Hi [Stakeholder],

Thanks for taking the time to review our AI-powered Security Operations Center today.

Key Highlights:
• Autonomous threat detection and response in seconds
• AI-powered analysis using Amazon Bedrock
• ~$200/month vs $200K/year traditional SOC
• Currently validated in dev environment

Dashboard Link: http://ai-soc-dev-dashboard-194561596031.s3-website.eu-central-1.amazonaws.com/

Next Steps:
1. [ ] Approval to deploy to production account
2. [ ] Confirm security team contacts for alerts
3. [ ] Schedule production deployment (Est. 2-4 weeks)

Let me know if you have any questions or need additional information.

Attached:
- Architecture diagram
- Cost breakdown
- Production deployment timeline

Best regards,
[Your name]
```

---

## Success Metrics to Highlight

**If moving to production, plan to track:**
- Mean Time to Detect (MTTD): Target <1 minute
- Mean Time to Respond (MTTR): Target <5 minutes  
- False Positive Rate: Target <5%
- Cost per event processed: Target <$0.01
- Security incidents prevented: Track monthly
- Compliance audit improvements: Document quarterly

---

## Quick Reference - Demo URLs

**Dashboard:** http://ai-soc-dev-dashboard-194561596031.s3-website.eu-central-1.amazonaws.com/

**API Endpoint:** https://rstevhgym8.execute-api.eu-central-1.amazonaws.com/threats

**AWS Console Links:**
- Step Functions: https://eu-central-1.console.aws.amazon.com/states/home?region=eu-central-1
- DynamoDB: https://eu-central-1.console.aws.amazon.com/dynamodbv2/home?region=eu-central-1#table?name=ai-soc-dev-state
- Lambda Functions: https://eu-central-1.console.aws.amazon.com/lambda/home?region=eu-central-1#/functions

**Generate more test data before demo:**
```bash
cd /home/jquintana-arroyo/git/AI_SOC
source .venv/bin/activate
python3 scripts/inject_test_events.py --count 25
```
