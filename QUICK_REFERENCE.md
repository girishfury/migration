# Quick Reference Guide

Fast lookup for common commands, configurations, and troubleshooting.

## File Locations

| Item | Path |
|------|------|
| Lambda Functions | `lambdas/*.py` |
| Common Utilities | `lambdas/common/` |
| Schemas | `lambdas/schemas/` |
| Terraform Files | `terraform/` |
| Documentation | `docs/` |
| CI/CD Workflow | `.github/workflows/deploy.yml` |
| Tests | `lambdas/tests/` |

## Quick Start Commands

```bash
# Setup environment
cd migration
python -m venv venv
source venv/bin/activate
pip install -r lambdas/requirements.txt

# Deploy infrastructure
cd terraform
terraform init -backend-config="bucket=your-bucket"
terraform plan -out=tfplan
terraform apply tfplan

# Test locally
cd ../lambdas
pytest tests/ -v

# Deploy Lambda
cd ..
aws lambda update-function-code \
  --function-name ingress-handler \
  --zip-file fileb://lambda-packages/ingress_handler.zip

# Monitor
aws logs tail /aws/lambda --follow
```

## Environment Variables

```bash
export AWS_REGION="us-east-1"
export TF_VAR_project_name="migration-orchestration"
export TF_VAR_environment="dev"
export EVENTBRIDGE_BUS_NAME="migration-bus"
export DYNAMODB_TABLE_NAME="migration-state"
export SQS_QUEUE_URL="https://sqs.region.amazonaws.com/account/queue"
export DEBUG="false"
```

## Lambda Functions Quick Reference

| Function | Trigger | Input | Output | Timeout |
|----------|---------|-------|--------|---------|
| ingress_handler | SQS | Message | EventBridge | 60s |
| validate_input | EventBridge | Event | Status | 60s |
| prepare_source | EventBridge | Event | Status | 300s |
| trigger_migration | EventBridge | Event | Status | 60s |
| verify_migration | EventBridge | Event | Status | 300s |
| finalize_cutover | EventBridge | Event | Success | 300s |
| callback_handler | EventBridge | Event | HTTP | 30s |
| rollback_handler | EventBridge | Event | Rollback | 300s |

## Common AWS CLI Commands

### SQS Operations

```bash
# Send message
aws sqs send-message \
  --queue-url <URL> \
  --message-body file://payload.json

# Receive messages
aws sqs receive-message --queue-url <URL> --max-number-of-messages 10

# Check queue
aws sqs get-queue-attributes \
  --queue-url <URL> \
  --attribute-names All

# Check DLQ
aws sqs receive-message --queue-url <DLQ_URL>
```

### Lambda Operations

```bash
# List functions
aws lambda list-functions --query 'Functions[*].[FunctionName,Runtime]'

# Get function config
aws lambda get-function-configuration --function-name <name>

# Update code
aws lambda update-function-code \
  --function-name <name> \
  --zip-file fileb://function.zip

# Invoke function
aws lambda invoke \
  --function-name <name> \
  --payload '{}' \
  response.json && cat response.json

# Get logs
aws logs tail /aws/lambda/<name> --follow
```

### Step Functions Operations

```bash
# List state machines
aws stepfunctions list-state-machines

# Describe state machine
aws stepfunctions describe-state-machine \
  --state-machine-arn <ARN>

# Start execution
aws stepfunctions start-execution \
  --state-machine-arn <ARN> \
  --input file://input.json

# Describe execution
aws stepfunctions describe-execution --execution-arn <ARN>

# Get history
aws stepfunctions get-execution-history --execution-arn <ARN>

# Stop execution
aws stepfunctions stop-execution --execution-arn <ARN>
```

### DynamoDB Operations

```bash
# Scan table
aws dynamodb scan --table-name migration-state

# Get item
aws dynamodb get-item \
  --table-name migration-state \
  --key '{"migrationId":{"S":"mig-12345"}}'

# Query by wave
aws dynamodb query \
  --table-name migration-state \
  --index-name waveIndex \
  --key-condition-expression "wave = :w" \
  --expression-attribute-values '{":w":{"S":"wave-3"}}'

# Update item
aws dynamodb update-item \
  --table-name migration-state \
  --key '{"migrationId":{"S":"mig-12345"}}' \
  --update-expression "SET #s = :status" \
  --expression-attribute-names '{"#s":"status"}' \
  --expression-attribute-values '{":status":{"S":"COMPLETED"}}'
```

### EventBridge Operations

```bash
# List rules
aws events list-rules --event-bus-name migration-bus

# List targets
aws events list-targets-by-rule \
  --rule <rule-name> \
  --event-bus-name migration-bus

# Send test event
aws events put-events \
  --entries '[{"Source":"migration.test","DetailType":"Test","Detail":"{}","EventBusName":"migration-bus"}]'
```

### CloudWatch Logs

```bash
# Tail logs
aws logs tail /aws/lambda/<function-name> --follow

# Filter logs
aws logs filter-log-events \
  --log-group-name /aws/lambda \
  --filter-pattern "ERROR"

# Get insights
aws logs start-query \
  --log-group-name /aws/lambda \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/'
```

## Test Message Templates

### Valid Migration Request

```json
{
  "migrationId": "mig-12345",
  "appName": "billing-app",
  "source": "azure",
  "target": "aws",
  "environment": "prod",
  "wave": "wave-3",
  "steps": ["freeze", "replicate", "validate", "switch"],
  "sourceVmId": "vm-123456",
  "targetVmName": "billing-app-prod-01",
  "instanceType": "t3.large",
  "subnetId": "subnet-12345",
  "securityGroupIds": ["sg-12345"],
  "callbackUrl": "https://example.com/callback",
  "tags": {
    "Environment": "prod",
    "Application": "billing",
    "Owner": "platform-team"
  }
}
```

### Invalid Message (for testing error handling)

```json
{
  "appName": "test-app"
  // Missing required fields
}
```

## Common Troubleshooting Commands

```bash
# Check Lambda error rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=<name> \
  --statistics Sum \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300

# Check DLQ messages
aws sqs get-queue-attributes \
  --queue-url <DLQ_URL> \
  --attribute-names ApproximateNumberOfMessages

# Check replication lag
aws mgn describe-source-servers \
  --query 'items[*].[sourceServerID,replicationStatus.replicationLagSec]'

# Check Step Functions failures
aws stepfunctions list-executions \
  --state-machine-arn <ARN> \
  --status-filter FAILED \
  --max-items 10

# Check for stuck executions
aws stepfunctions list-executions \
  --state-machine-arn <ARN> \
  --status-filter RUNNING \
  --query 'executions[?startDate < `'$(date -d '2 hours ago' +%s)'000`]'
```

## Terraform Quick Commands

```bash
# Initialize
terraform init -backend-config="bucket=<bucket>"

# Validate
terraform validate

# Plan
terraform plan -out=tfplan -var-file=environments/dev.tfvars

# Apply
terraform apply tfplan

# Destroy
terraform destroy -var-file=environments/dev.tfvars

# Get output
terraform output -json > outputs.json

# Get specific output
terraform output -raw sqs_queue_url

# Import resource
terraform import aws_lambda_function.ingress_handler ingress-handler

# Refresh state
terraform refresh

# Format code
terraform fmt -recursive
```

## Python Testing Commands

```bash
# Run all tests
pytest lambdas/tests/ -v

# Run specific test
pytest lambdas/tests/test_ingress_handler.py::test_validate_message_valid_payload -v

# Run with coverage
pytest lambdas/tests/ -v --cov=lambdas --cov-report=html

# Run with output
pytest lambdas/tests/ -v -s

# Run specific marker
pytest lambdas/tests/ -v -m unit

# Lint code
flake8 lambdas/ --count --select=E9,F63,F7,F82

# Check style
black lambdas/ --check

# Type check
mypy lambdas/ --ignore-missing-imports
```

## GitHub Actions Commands

```bash
# View workflow runs
gh run list -L 10

# View workflow status
gh run view <run-id>

# View job logs
gh run view <run-id> --log

# Re-run failed jobs
gh run rerun <run-id>

# Cancel run
gh run cancel <run-id>

# List secrets
gh secret list

# Set secret
gh secret set AWS_ROLE_TO_ASSUME -b "arn:aws:iam::..."
```

## Error Messages & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `ValidationError` | Schema mismatch | Check payload against `migration_payload.json` |
| `PrerequisiteError` | Missing AWS resources | Verify subnets, security groups exist |
| `SourcePreparationError` | MGN agent not installed | Install MGN replication agent |
| `MigrationExecutionError` | MGN API failure | Check MGN status, permissions |
| `VerificationError` | Replication lag too high | Increase bandwidth, reduce source load |
| `CutoverError` | Cutover process failed | Check logs, DNS records |
| `RollbackError` | Rollback failed | Verify source still exists |
| `CALLBACK_FAILED` | External system unreachable | Check URL, network connectivity |
| `ProvisionedThroughputExceededException` | DynamoDB throttled | Switch to on-demand or increase capacity |
| `ThrottlingException` | AWS API throttled | Implement exponential backoff |

## Performance Benchmarks

| Operation | Typical Duration |
|-----------|------------------|
| SQS → EventBridge | < 1 second |
| EventBridge → Lambda | < 5 seconds |
| Lambda cold start | 1-3 seconds |
| Lambda warm execution | < 500ms |
| Step Functions transition | < 1 second |
| DynamoDB write | < 100ms |
| DynamoDB read | < 50ms |
| Complete migration | 30-120 minutes |

## Resource Limits (AWS Defaults)

| Resource | Limit | Notes |
|----------|-------|-------|
| Lambda function timeout | 900s (15 min) | Increase for long migrations |
| Lambda memory | 10GB | Sufficient for this workload |
| DynamoDB item size | 400KB | Archive large data to S3 |
| SQS message size | 256KB | Use SQS to S3 pattern if larger |
| Step Functions execution duration | 1 year | More than sufficient |
| EventBridge rules per account | 300 | Increase if needed |
| Lambda concurrent executions | 1000 | Request increase for scale |

## Documentation Index

| Document | Purpose | Audience |
|----------|---------|----------|
| README.md | Quick start & overview | Everyone |
| ARCHITECTURE.md | System design details | Architects, Engineers |
| RUNBOOK.md | Operations procedures | Operations, SRE |
| FILES_SUMMARY.md | Code file reference | Developers |
| DEPLOYMENT_CHECKLIST.md | Pre-deployment checklist | DevOps, QA |
| QUICK_REFERENCE.md | This document | Everyone |

## URLs & Endpoints (Update as needed)

```
AWS Console:         https://console.aws.amazon.com
Terraform State:     s3://migration-terraform-state
GitHub Repository:   https://github.com/yourorg/migration
Slack Channel:       #migration-alerts
Status Page:         https://status.yourcompany.com
```

## Contact & Escalation

| Role | Name | Email | Phone |
|------|------|-------|-------|
| On-Call Engineer | TBD | on-call@example.com | +1-XXX-XXX-XXXX |
| Engineering Manager | TBD | manager@example.com | +1-XXX-XXX-XXXX |
| VP Engineering | TBD | vp@example.com | +1-XXX-XXX-XXXX |

## Emergency Procedures

### Complete System Failure

1. Page on-call engineer immediately
2. Disable GitHub Actions to prevent more deployments
3. Stop all running Step Functions executions
4. Disable all SQS consumer Lambda functions
5. Document incident in incident channel
6. Begin root cause analysis
7. Execute rollback if safe

### Data Loss

1. Restore DynamoDB from backup:
   ```bash
   aws dynamodb restore-table-to-point-in-time \
     --source-table-name migration-state \
     --target-table-name migration-state-restored \
     --restore-date-time $(date -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)
   ```
2. Verify data integrity
3. Rename tables if needed
4. Notify stakeholders

### Security Incident

1. Immediately disable affected Lambda function
2. Rotate all credentials and secrets
3. Review CloudTrail logs for suspicious activity
4. Engage security team
5. Update security group rules if needed
6. Update incident log with all details

---

**Last Updated**: 2024-01-XX  
**Version**: 1.0  
**Maintainer**: Platform Team
