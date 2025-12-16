#!/bin/bash
# Quick deployment script for dashboard to S3

set -e

# Configuration
S3_BUCKET="ai-soc-dev-dashboard-194561596031"
AWS_REGION="eu-central-1"
STACK_NAME="ai-soc-dashboard-dev"

echo "🚀 Deploying AI-SOC Dashboard to S3..."
echo "   Bucket: $S3_BUCKET"
echo "   Region: $AWS_REGION"
echo ""

# Get API endpoint from CloudFormation
echo "📡 Fetching API endpoint from CloudFormation..."
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $AWS_REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -z "$API_ENDPOINT" ]; then
  echo "⚠️  Warning: Could not retrieve API endpoint from CloudFormation"
  echo "   Using existing configuration in index.html"
  USE_EXISTING=true
else
  echo "✅ Found API endpoint: $API_ENDPOINT"
  USE_EXISTING=false
fi

# Create temp file with updated API endpoint if needed
if [ "$USE_EXISTING" = false ]; then
  echo "🔧 Updating API endpoint in index.html..."
  # Replace the hardcoded API endpoint with the one from CloudFormation
  sed "s|https://rstevhgym8.execute-api.eu-central-1.amazonaws.com|${API_ENDPOINT}|g" \
    dashboard/static/index.html > /tmp/index_deploy.html
  DEPLOY_FILE="/tmp/index_deploy.html"
else
  DEPLOY_FILE="dashboard/static/index.html"
fi

# Upload to S3
echo "📤 Uploading index.html to S3..."
aws s3 cp $DEPLOY_FILE s3://$S3_BUCKET/index.html \
  --region $AWS_REGION \
  --cache-control "public, max-age=300" \
  --content-type "text/html"

# Clean up temp file
if [ -f "/tmp/index_deploy.html" ]; then
  rm /tmp/index_deploy.html
fi

# Get the website URL
WEBSITE_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $AWS_REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \
  --output text 2>/dev/null || echo "http://$S3_BUCKET.s3-website.$AWS_REGION.amazonaws.com")

echo ""
echo "✅ Dashboard deployed successfully!"
echo "🌐 Dashboard URL: $WEBSITE_URL"
echo ""
echo "💡 Tip: It may take a few seconds for the changes to appear due to caching."

