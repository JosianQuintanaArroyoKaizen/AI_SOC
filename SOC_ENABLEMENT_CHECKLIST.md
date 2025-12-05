# SOC Enablement Checklist

Use this checklist to drive the repo from "code deployed" to "autonomous SOC in production". Each section lists the concrete verifications or follow-up work required. Mark items off in order; many depend on outputs from prior sections.

## 1. AWS & Artifact Prereqs
- [ ] Artifact bucket created (`soc-artifacts-<env>`) with versioning + encryption.
- [ ] CloudFormation templates uploaded under `templates/` prefix (or packaged by CI job).
- [ ] Model artifact uploaded to S3 and parameter file (`cloudformation/parameters/<env>.json`) points to it.
- [ ] Bedrock access enabled in `eu-central-1` (service quota + opt-in confirmed).
- [ ] GitHub secrets set: `AWS_ROLE_TO_ASSUME`, `ALERT_EMAIL`, optional `PROJECT_NAME` override.

## 2. CI/CD Pipelines
- [ ] `Deploy Infrastructure` workflow completes for target branch/environment.
- [ ] `Deploy Lambda Functions` workflow finishes with artifacts uploaded to the foundation stack bucket.
- [ ] `run-tests` workflow green (unit + integration) to ensure lambdas stay regression-free.
- [ ] Workflow dispatch docs updated with environment options (dev/staging/prod) so on-call knows how to rerun.

## 3. Stack Validation (per environment)
For each nested stack (`foundation`, `ingestion`, `storage`, `ml-inference`, `remediation`, `orchestration`):
- [ ] `aws cloudformation describe-stacks --stack-name ai-soc-<stack>-<env>` returns `*_COMPLETE`.
- [ ] Outputs captured in a shared doc/Parameter Store (Kinesis stream name, Lambda ARNs, DynamoDB table, Step Functions ARN, SNS topic, artifacts bucket, SageMaker endpoint name).
- [ ] IAM roles created by stacks have AWS Config or Security Hub approval (security review).

## 4. Lambda Artifacts & Configuration
- [ ] Confirm four zip files exist in S3: `lambda/event-normalizer.zip`, `alert-triage.zip`, `ml-inference.zip`, `remediation.zip`.
- [ ] Environment variables resolved at runtime (`KINESIS_STREAM_NAME`, `SAGEMAKER_ENDPOINT`, etc.).
- [ ] Dependency footprints verified (no unused large libraries) to keep package size < 50 MB.
- [ ] CloudWatch log groups created automatically; retention configured (14–30 days per policy).

## 5. Data Plane Smoke Tests
- [ ] Send sample GuardDuty/SecurityHub event via `aws events put-events` and watch `event-normalizer` logs for normalization success.
- [ ] Verify normalized payload arrives in Kinesis (`aws kinesis get-records` or temporary consumer Lambda).
- [ ] Trigger ML Lambda manually (`aws lambda invoke ...ml-inference`) with stored sample event to ensure SageMaker endpoint responds.
- [ ] Trigger alert-triage Lambda with output from ML step; confirm triage metadata appended.

## 6. SageMaker & ML Model
- [ ] Run `aws sagemaker describe-endpoint --endpoint-name <name>`; status must be `InService`.
- [ ] Load-test endpoint with at least 100 sequential invocations to confirm scaling/latency within SLA.
- [ ] Document model version, training dataset, and drift monitoring plan (tie back to `ml_training/` artifacts).

## 7. Step Functions Workflow
- [ ] Execute `ai-soc-<env>-soc` state machine with a representative event, confirm transitions ML → Triage → Bedrock/Remediation/SNS succeed.
- [ ] Confirm DynamoDB `state` table receives item with triage + remediation metadata.
- [ ] SNS alert email reaches `ALERT_EMAIL` inbox when `requires_human_review` path is taken.
- [ ] Bedrock call has proper IAM permissions and region availability (watch for throttling or opt-in errors).

## 8. Automated Remediation
- [ ] Provide test payload with `affected_user`, `access_key_id`, `security_group_id`, etc., and run remediation Lambda.
- [ ] Validate IAM changes (access key status, MFA device state) and EC2 security group revocations in AWS console.
- [ ] Ensure remediation role scoped minimally; document rollback steps if automation misfires.

## 9. Observability & Runbooks
- [ ] CloudWatch log groups aggregated in a dashboard (errors, throttles, duration metrics).
- [ ] OpenSearch Serverless collection reachable; index mapping set for alert documents.
- [ ] Grafana/Prometheus integration updated to scrape Lambda and SageMaker metrics (see `MONITORING_STACK_SUMMARY.md`).
- [ ] Runbook stored in `docs/operations/` covering manual failover and how to replay events.

## 10. Security & Compliance
- [ ] IAM Access Analyzer run on stack-created roles; findings triaged.
- [ ] Secrets (API keys, Bedrock settings) stored in AWS Secrets Manager or SSM Parameter Store—never plaintext in repo.
- [ ] Enable CloudTrail data events for Lambda/S3 per security guide recommendations.
- [ ] Conduct cost + security review before enabling production environment (link to `PRODUCTION_READINESS_ASSESSMENT.md`).

## 11. Go-Live Criteria
- [ ] All checkboxes above completed for target environment.
- [ ] Post-deployment test scenario executed end-to-end with success recorded.
- [ ] Stakeholders sign off in `DEPLOYMENT_STATUS.md` or equivalent doc.
- [ ] Monitoring alerts (PagerDuty/Slack) verified.

Once every section is checked, the repo fulfills the SOC functionality described in `AI_GUIDE_KAIZEN.md` and is ready for continuous operations.
