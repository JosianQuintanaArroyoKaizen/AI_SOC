# Getting Started with AI-SOC (CI/CD Edition)

The quickest way to experience AI-SOC is now through **GitHub Actions + AWS CloudFormation** in `eu-central-1`. Local Docker orchestration has been retired; every environment is created as infrastructure-as-code and deployed through the automated pipelines documented in `AI_GUIDE_KAIZEN.md` and `CICD_GUIDE.md`.

Use this guide as the fast path to configure accounts, trigger the workflows, and validate your first deployment.

---

## 1. Prerequisites

### Accounts & Permissions
- **AWS Account** with permissions to create IAM, CloudFormation, Lambda, SageMaker, OpenSearch, and Step Functions resources in `eu-central-1`.
- **GitHub Repository Access** with admin rights to configure Actions secrets and OIDC trust (fork or clone `zhadyz/AI_SOC`).

### Local Tooling (for validation or troubleshooting)
- Git 2.40+
- Python 3.11 (used for optional Lambda packaging tests)
- AWS CLI v2 with a profile that can create stacks in `eu-central-1`
- cfn-lint / cfn-guard (optional but recommended)

> ⚠️ Docker Desktop is **not** required. All services run in AWS once deployed.

---

## 2. Bootstrap Checklist

| Step | What | Reference |
|------|------|-----------|
| 1 | Clone repo locally (`git clone https://github.com/YOUR_ORG/AI_SOC.git`) | This guide |
| 2 | Deploy the GitHub OIDC stack (`cloudformation/00-github-oidc.yaml`) so Actions can assume an AWS role | `AI_GUIDE_KAIZEN.md` |
| 3 | Create GitHub Secrets: `AWS_ROLE_TO_ASSUME`, `AWS_ACCOUNT_ID`, `AWS_REGION=eu-central-1`, `ALERT_EMAIL` | `CICD_GUIDE.md` |
| 4 | (Optional) Run `scripts/validate-cfn.sh` locally to lint templates before pushing | local workstation |
| 5 | Push changes/parameters to `main`/`develop` or trigger `workflow_dispatch` to deploy | GitHub Actions |
| 6 | Monitor stack creation in CloudFormation console (root stack + nested stacks) | AWS Console |
| 7 | Validate services (Lambda ARNs, SageMaker endpoint, Step Functions state machines, OpenSearch collection) | AWS Console |

---

## 3. Repository Tour

- `cloudformation/` – Root + nested stack templates (foundation, ingestion, storage, ML, orchestration, monitoring).
- `lambda/` – Python sources packaged by the `deploy-lambdas` workflow.
- `.github/workflows/` – GitHub Actions for infrastructure deploy, Lambda packaging, and automated testing.
- `docs/` – MkDocs site with architecture, deployment, and security deep dives.

When in doubt, consult `AI_GUIDE_KAIZEN.md` for architectural rationale and `CICD_GUIDE.md` for exact workflow configuration.

---

## 4. Configure AWS <-> GitHub Trust

1. Sign in to AWS with an administrator role.
2. Deploy the OIDC bootstrap stack (one-time):

```bash
aws cloudformation deploy \
	--template-file cloudformation/00-github-oidc.yaml \
	--stack-name github-oidc-setup \
	--parameter-overrides \
			GitHubOrg=YOUR_ORG \
			GitHubRepo=AI_SOC \
	--capabilities CAPABILITY_NAMED_IAM \
	--region eu-central-1
```

3. Capture the exported `RoleArn` and store it in the repository secret `AWS_ROLE_TO_ASSUME`.

---

## 5. Configure GitHub Secrets & Variables

Navigate to **Settings → Secrets and variables → Actions** and add:

| Name | Value |
|------|-------|
| `AWS_ACCOUNT_ID` | Your 12-digit account ID |
| `AWS_REGION` | `eu-central-1` |
| `AWS_ROLE_TO_ASSUME` | Role ARN from the bootstrap stack |
| `ALERT_EMAIL` | Distribution list for SNS alerts |

Optional organization-level secrets can store shared ARNs or artifact bucket names if you operate multiple environments.

---

## 6. Prepare Environment Parameters

Each environment (`dev`, `staging`, `prod`) consumes a JSON parameter file under `cloudformation/parameters/`. Update values such as VPC IDs, subnet lists, SageMaker instance sizes, and Step Functions log buckets. Keep sensitive data in AWS SSM Parameter Store or Secrets Manager instead of committing plaintext secrets.

---

## 7. Trigger the Pipelines

### Automatic (recommended)
1. Commit your template or Lambda changes.
2. Push to `main` or `develop` (or open a PR targeting `main`).
3. GitHub Actions runs in this order:
	 - `deploy-infra.yml`: validates templates, deploys foundation + nested stacks.
	 - `deploy-lambdas.yml`: packages each Lambda and uploads artifacts to the S3 bucket from the foundation stack.
	 - `run-tests.yml`: executes unit + integration suites; failures block promotion.

### Manual (workflow_dispatch)
Use the Actions tab → select the workflow → **Run workflow** → choose `dev`, `staging`, or `prod`. This is useful for hotfix redeployments without new commits.

---

## 8. Validate the Deployment

1. **CloudFormation Console** (`eu-central-1`): ensure `ai-soc-foundation-*`, `ai-soc-ingestion-*`, `ai-soc-storage-*`, etc., show `CREATE_COMPLETE`.
2. **S3**: verify the artifacts bucket contains Lambda ZIPs under `lambda/<function>.zip`.
3. **Lambda**: confirm environment variables and last modified times reflect your deployment.
4. **SageMaker Serverless Endpoint**: check the inference endpoint status is `InService`.
5. **OpenSearch Serverless**: ensure the collection is active and accessible through the network policy defined in `03-storage.yaml`.
6. **Step Functions**: run a test execution through the orchestration state machine to validate event flow end-to-end.

For expected outputs and stack relationships, review `AI_GUIDE_KAIZEN.md` (Architecture → Stack Hierarchy).

---

## 9. Day-2 Operations

- **Change Management**: every pull request should include template diffs and `cfn-lint` output. Use the `cfn-plan` job (if enabled) or `aws cloudformation create-change-set` locally to preview breaking changes.
- **Rollback**: re-run the `deploy-infra` workflow with the last known-good commit or delete the failed stack change set to maintain stability.
- **Secrets Rotation**: store sensitive parameters in AWS Secrets Manager and reference them via dynamic resolution in templates.
- **Monitoring**: the `06-monitoring.yaml` stack creates CloudWatch dashboards and alarms. Subscribe additional targets to the exported SNS topic for 24/7 alerting.

---

## 10. Troubleshooting

### GitHub Actions Cannot Assume Role
- Confirm the OIDC provider thumbprint and repository filters in `00-github-oidc.yaml` match your org/repo.
- Re-run the bootstrap stack after renaming the GitHub repository.

### CloudFormation Stack Failure
- Use `aws cloudformation describe-stack-events --stack-name ai-soc-foundation-dev` for detailed failure reasons.
- Ensure service quotas (Lambda concurrency, SageMaker endpoint count, VPC limits) are not exceeded in `eu-central-1`.

### Lambda Packaging Issues
- Check the `deploy-lambdas` workflow logs for missing dependencies or mismatched Python versions.
- Use `python -m pip install -r lambda/<function>/requirements.txt -t lambda/<function>` locally to reproduce packaging errors.

### Integration Tests Failing
- Review `tests/integration/test_workflow.py` for required environment variables.
- Ensure GuardDuty and Security Hub are enabled in the AWS account so sample events flow through EventBridge.

---

## 11. FAQ

**What happened to Docker Desktop and the local launcher?**  
The platform now deploys directly into AWS. Use the updated `AI-SOC-Launcher.py` (Deployment Assistant) if you want a desktop helper for running pre-flight checks, linting templates, or opening the GitHub Actions dashboard.

**Can I still run parts of the stack locally?**  
Yes, but it is no longer the supported path. If you need local experiments, run individual Lambda handlers with `pytest` or the AWS SAM CLI without altering this guide.

**Why eu-central-1?**  
All reference templates, SNS topics, SageMaker serverless, and OpenSearch Serverless quotas were validated for `eu-central-1`. Adjust the `AWS_REGION` secret and parameter files only if you have confirmed service availability in another region.

---

You are ready to deploy. Commit, push, watch the pipelines, and dive into `AI_GUIDE_KAIZEN.md` for deeper architectural insight.
