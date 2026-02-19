# Setup Guide for Event-Driven Migration Orchestration Framework

## Prerequisites Checklist

### AWS Account Setup
- [ ] AWS account with appropriate permissions
- [ ] AWS MGN service enabled and configured
- [ ] Cloud Migration Factory (CMF) set up
- [ ] S3 bucket created for Terraform state (e.g., `your-org-terraform-state`)
- [ ] DynamoDB table created for Terraform locks (e.g., `terraform-locks`)
- [ ] AWS CLI v2 installed and configured
- [ ] Terraform >= 1.5.0 installed

### GitHub Setup
- [ ] GitHub repository created
- [ ] GitHub OIDC provider configured in AWS IAM
- [ ] GitHub Secrets created:
  - `AWS_ROLE_ARN`: ARN of IAM role for GitHub OIDC
  - `TF_STATE_BUCKET`: Name of S3 bucket for Terraform state
  - `SLACK_WEBHOOK` (optional): Slack webhook for notifications

### Local Setup
- [ ] Python 3.11+ installed
- [ ] Clone repository: `git clone <repo-url>`
- [ ] Create Python virtual environment: `python3 -m venv venv`
- [ ] Activate virtual environment: `source venv/bin/activate`
- [ ] Install Python dependencies: `pip install -r lambdas/requirements.txt`

## Step 1: Configure AWS IAM for GitHub OIDC

### Create GitHub OIDC Provider (One-time setup)

```bash
aws iam create-open-id-connect-provider \
    --url "https://token.actions.githubusercontent.com" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" # Get from GitHub
```

### Create IAM Role for Deployment

```bash
cat > trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/YOUR_REPO:*"
        }
      }
    }
  ]
}
EOF

aws iam create-role \
    --role-name github-migration-deployer \
    --assume-role-policy-document file://trust-policy.json

# Attach permissions
aws iam attach-role-policy \
    --role-name github-migration-deployer \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

## Step 2: Create S3 Bucket for Terraform State

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="your-org-terraform-state-${ACCOUNT_ID}"

# Create bucket
aws s3api create-bucket \
    --bucket ${BUCKET_NAME} \
    --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket ${BUCKET_NAME} \
    --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
    --bucket ${BUCKET_NAME} \
    --server-side-encryption-configuration '{
      "Rules": [{
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }]
    }'

# Block public access
aws s3api put-public-access-block \
    --bucket ${BUCKET_NAME} \
    --public-access-block-configuration \
      BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

## Step 3: Configure GitHub Secrets

```bash
# Get AWS Account ID and Role ARN
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/github-migration-deployer"

# Using GitHub CLI
gh secret set AWS_ACCOUNT_ID -b "${ACCOUNT_ID}"
gh secret set AWS_ROLE_ARN -b "${ROLE_ARN}"
gh secret set TF_STATE_BUCKET -b "${BUCKET_NAME}"

# Optional: Slack webhook
gh secret set SLACK_WEBHOOK -b "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

## Step 4: Configure Terraform Variables

### For Development Environment

```bash
cd terraform

# Copy dev template
cp terraform.dev.tfvars terraform.tfvars

# Edit with your values
vim terraform.tfvars
```

Update the following values:
- `REPLACE_WITH_YOUR_BUCKET` → Your S3 bucket name
- `region` → Your preferred AWS region
- `project_name` → Your project name

### For Production Environment

```bash
cp terraform.prod.tfvars terraform.tfvars.prod

# Edit with production values
vim terraform.tfvars.prod
```

## Step 5: Initialize Terraform

```bash
cd terraform

# Initialize Terraform
terraform init \
    -backend-config="bucket=${BUCKET_NAME}" \
    -backend-config="key=event-driven-migration/terraform.tfstate" \
    -backend-config="region=us-east-1"

# Validate configuration
terraform validate

# Plan deployment
terraform plan -var-file=terraform.tfvars -out=tfplan
```

## Step 6: Deploy to Development

### Option A: Deploy via GitHub Actions (Recommended)

```bash
# Push to develop branch
git push origin develop

# GitHub Actions will automatically:
# 1. Run Terraform plan
# 2. Build Lambda functions
# 3. Run tests
# 4. Deploy to dev environment
```

### Option B: Deploy Locally

```bash
cd terraform

# Apply Terraform configuration
terraform apply tfplan

# Get outputs
terraform output -json > outputs.json
cat outputs.json
```

## Step 7: Configure Lambda Functions

### Install Dependencies

```bash
cd lambdas

# Install Python dependencies for local testing
pip install -r requirements.txt

# Build Lambda packages (if deploying locally)
pip install --target package boto3 aws-xray-sdk jsonschema requests python-json-logger

# Create deployment package
zip -r function.zip . -x "tests/*" "__pycache__/*"
```

### Update Environment Variables

Lambda functions get environment variables from Terraform:
- `DYNAMODB_TABLE`: Migration state table name
- `KMS_KEY_ID`: KMS key for encryption
- `SNS_TOPIC_ARN`: SNS topic for notifications

These are automatically set by Terraform.

## Step 8: Verify Deployment

```bash
# Get API Gateway endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name migration-orchestration \
    --query 'Stacks[0].Outputs[?OutputKey==`APIEndpoint`].OutputValue' \
    --output text)

# Test API endpoint
curl -X POST ${API_ENDPOINT}/migrations \
    -H "Content-Type: application/json" \
    -d '{
      "migrationId": "mig-test-001",
      "appName": "test-app",
      "source": "azure",
      "target": "aws",
      "environment": "dev",
      "wave": "wave-1",
      "callbackUrl": "https://example.com/callback"
    }'
```

## Step 9: Run Tests

### Unit Tests

```bash
cd lambdas
pytest tests/unit/ -v --cov=.
```

### Integration Tests

```bash
cd lambdas
pytest tests/integration/ -v --tb=short
```

### Terraform Tests

```bash
cd terraform
terraform validate
terraform plan -json | jq .
```

## Step 10: Configure CloudWatch Monitoring

### Create SNS Topic for Alerts

```bash
# Create SNS topic
aws sns create-topic --name migration-alerts

# Subscribe your email
aws sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:migration-alerts \
    --protocol email \
    --notification-endpoint your-email@example.com
```

### Enable CloudWatch Alarms

Terraform automatically creates alarms for:
- DLQ message count
- DynamoDB throttling
- Lambda errors

View them in CloudWatch Console.

## Step 11: Configure CMF Integration

### Update CMF Settings

```bash
# Set CMF wave status in SSM Parameter Store
aws ssm put-parameter \
    --name "/migration/cmf/wave/wave-1/status" \
    --value '{"status":"active","created":"2024-01-01"}' \
    --type String \
    --overwrite
```

## Step 12: Production Deployment

### Pre-Production Checklist

- [ ] All tests pass in dev environment
- [ ] CloudWatch logs reviewed for errors
- [ ] Database replication verified
- [ ] API endpoint tested with sample payloads
- [ ] Backup and disaster recovery verified
- [ ] Security review completed

### Deploy to Production

```bash
# Create production branch
git checkout -b production/release-1.0

# Push to production
git push origin production/release-1.0

# GitHub Actions will:
# 1. Require manual approval in production environment
# 2. Run all tests
# 3. Deploy to production
# 4. Send notifications to Slack
```

## Troubleshooting Setup Issues

### Terraform State Lock

```bash
# If state is locked, unlock it
terraform force-unlock <LOCK_ID>
```

### GitHub OIDC Issues

```bash
# Verify OIDC provider
aws iam list-open-id-connect-providers

# Check assume role trust
aws iam get-role --role-name github-migration-deployer
```

### Lambda Package Issues

```bash
# Verify Lambda package
unzip -t function.zip | head -20

# Check function code
aws lambda get-function --function-name migration-orchestration-ingress-handler
```

### API Gateway Issues

```bash
# Check API endpoint
aws apigateway get-rest-apis

# Test API directly
aws apigateway test-invoke-method \
    --rest-api-id <API_ID> \
    --resource-id <RESOURCE_ID> \
    --http-method POST \
    --body '{...}'
```

## Next Steps

1. [Deploy to Development Environment](#step-6-deploy-to-development)
2. [Review ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design
3. [Check RUNBOOK.md](docs/RUNBOOK.md) for operational procedures
4. [Monitor Dashboard](https://console.aws.amazon.com/cloudwatch/)

## Support

For issues or questions:
1. Check [RUNBOOK.md](docs/RUNBOOK.md) for troubleshooting
2. Review CloudWatch logs: `/aws/migration/migration-orchestration`
3. Check GitHub Actions workflow logs
4. Contact your platform team

## Security Best Practices

- [ ] Rotate AWS credentials regularly
- [ ] Review IAM policies quarterly
- [ ] Enable MFA for AWS console access
- [ ] Audit CloudTrail logs monthly
- [ ] Test disaster recovery procedures
- [ ] Keep Terraform state encrypted
- [ ] Use separate AWS accounts for dev/prod
