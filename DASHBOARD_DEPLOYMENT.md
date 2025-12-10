# Dashboard Deployment Fix

## What Happened?

Your S3 bucket was deploying the **OnyxLab marketing website** (`docs/` directory) instead of the **AI-SOC Threat Dashboard** (`dashboard/templates/` directory).

## What Was Fixed?

1. **Updated CI/CD Pipeline** (`.github/workflows/deploy-s3-frontend.yml`)
   - Now deploys `dashboard/templates/threats.html` instead of `docs/`
   - Automatically retrieves and configures the API Gateway endpoint
   - Copies `threats.html` as `index.html` for the S3 static website

2. **Updated Dashboard HTML** (`dashboard/templates/threats.html`)
   - Added automatic API endpoint configuration
   - Works with both local Flask development and S3 deployment
   - Detects environment and uses appropriate API URL

## Deploy the Fix

### Option 1: Automatic (via GitHub Actions)
```bash
git add .
git commit -m "Fix: Deploy threat dashboard instead of OnyxLab site"
git push origin master
```

The CI/CD pipeline will automatically:
- Deploy the threat dashboard to S3
- Configure the API Gateway endpoint
- Make it available at: http://ai-soc-dev-dashboard-194561596031.s3-website-us-east-1.amazonaws.com

### Option 2: Manual Deployment
```bash
# Get the API endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name ai-soc-dev-dashboard \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text)

# Update the HTML with the API endpoint
sed -i "s|: 'https://YOUR_API_ID.execute-api.YOUR_REGION.amazonaws.com'|: '${API_ENDPOINT}'|g" \
  dashboard/templates/threats.html

# Deploy to S3
aws s3 cp dashboard/templates/threats.html \
  s3://ai-soc-dev-dashboard-194561596031/index.html \
  --cache-control "public, max-age=300" \
  --content-type "text/html"
```

## Dashboard Features

Your threat dashboard now includes:

### 🎯 Tabbed Interface
- **Critical** - Highest priority threats (red)
- **High** - High priority threats (orange)
- **Medium** - Medium priority threats (yellow)
- **Low** - Low priority threats (blue)

### 🔍 Filtering & Sorting
Within each tab:
- **Search** by event type, alert ID, or source
- **Sort** by priority score, timestamp, or threat score

### 📊 Real-time Stats
- Total threats count
- Counts by severity level
- Auto-remediated threats count

### 🤖 AI Analysis
Each threat card shows:
- Claude 3.7 Sonnet AI analysis
- Risk scores and attack vectors
- Recommended remediation actions

## API Endpoints

The dashboard connects to these API Gateway endpoints:
- `GET /threats` - Retrieve all threat alerts
- `GET /stats` - Get summary statistics

## Troubleshooting

### Dashboard shows "Loading..." forever
1. Check that the API Gateway is deployed: `aws cloudformation describe-stacks --stack-name ai-soc-dev-dashboard`
2. Verify the API endpoint is accessible
3. Check browser console for CORS or network errors

### API endpoint not configured
If the dashboard can't find the API, manually update line 195 in `dashboard/templates/threats.html`:
```javascript
const API_BASE_URL = 'YOUR_API_GATEWAY_URL_HERE';
```

### Need the OnyxLab site?
The marketing site is still in `docs/` - you can:
1. Deploy it to a different S3 bucket
2. Use GitHub Pages for the docs site
3. Create a subdirectory structure (e.g., `/dashboard` and `/docs`)

## Next Steps

1. Commit and push the changes
2. Wait for GitHub Actions to complete
3. Visit your S3 website URL
4. Verify the threat dashboard loads correctly
5. Test filtering and tab switching
