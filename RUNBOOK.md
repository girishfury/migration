# Operational Runbook

## Monitoring Dashboard

### Accessing CloudWatch Dashboard

1. Navigate to [CloudWatch Console](https://console.aws.amazon.com/cloudwatch/)
2. Click **Dashboards** in the left sidebar
3. Select `migration-orchestration-dashboard`

### Key Metrics to Monitor

| Metric | Threshold | Action |
|--------|-----------|--------|
| DLQ Message Count | > 0 | Investigate failed messages |
| Replication Lag | > 300s | Check network connectivity |
| Health Status | 0 (unhealthy) | Investigate application issues |
| Lambda Errors | > 5 | Review CloudWatch logs |
| DynamoDB Throttle | > 0 | Consider on-demand capacity |

## Daily Operations

### Morning Check-in

```bash
#!/bin/bash

# Check for failed migrations
aws sqs get-queue-attributes \
    --queue-url $(aws sqs get-queue-url --queue-name migration-orchestration-migration-requests-dlq --query QueueUrl --output text) \
    --attribute-names ApproximateNumberOfMessages

# Check Step Functions executions
aws states list-executions \
    --state-machine-arn arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:migration-orchestration-migration-orchestration \
    --status-filter FAILED

# Check Lambda error rates
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Errors \
    --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum
```

### Key Commands

#### View Migration Status

```bash
# Get all in-progress migrations
aws dynamodb scan \
    --table-name migration-orchestration-migration-state \
    --filter-expression "attribute_exists(#status) AND #status = :status" \
    --expression-attribute-names '{"#status":"status"}' \
    --expression-attribute-values '{":status":{"S":"IN_PROGRESS"}}'

# Get specific migration details
aws dynamodb get-item \
    --table-name migration-orchestration-migration-state \
    --key '{"migrationId":{"S":"mig-12345"}}'
```

#### View Step Functions Execution

```bash
# List recent executions
aws states list-executions \
    --state-machine-arn arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:migration-orchestration-migration-orchestration \
    --max-results 10 \
    --query 'executions[].{Name:name,Status:status,StartDate:startDate}'

# Get execution details
aws states describe-execution \
    --execution-arn arn:aws:states:us-east-1:ACCOUNT_ID:execution:migration-orchestration-migration-orchestration:EXECUTION_NAME

# Get execution history (all steps)
aws states get-execution-history \
    --execution-arn arn:aws:states:us-east-1:ACCOUNT_ID:execution:migration-orchestration-migration-orchestration:EXECUTION_NAME \
    --query 'events[].{Type:type,Timestamp:timestamp,Details:stateEnteredEventDetails.name}'
```

#### View Lambda Logs

```bash
# View recent Lambda logs with correlation ID
aws logs tail /aws/lambda/migration-orchestration-validate-input \
    --follow \
    --filter-pattern '{ $.correlationId = "mig-abc123" }'

# Export logs for analysis
aws logs create-export-task \
    --log-group-name /aws/lambda/migration-orchestration-ingress-handler \
    --from $(date -d '7 days ago' +%s)000 \
    --to $(date +%s)000 \
    --destination s3-bucket-name \
    --destination-prefix logs/lambda/
```

#### View SQS DLQ Messages

```bash
# Receive messages from DLQ (peek, 5 minutes visibility)
aws sqs receive-message \
    --queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/migration-orchestration-migration-requests-dlq \
    --max-number-of-messages 10 \
    --visibility-timeout 300

# Delete message after investigation
aws sqs delete-message \
    --queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/migration-orchestration-migration-requests-dlq \
    --receipt-handle MESSAGE_RECEIPT_HANDLE

# Move message back to main queue for retry
aws sqs send-message \
    --queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/migration-orchestration-migration-requests \
    --message-body "$(aws sqs receive-message ... --output json | jq -r '.Messages[0].Body')"
```

## Incident Response

### DLQ Has Messages

**Symptoms**: DLQ message count > 0

**Investigation Steps**:

```bash
# 1. Get message from DLQ
aws sqs receive-message \
    --queue-url $(aws sqs get-queue-url --queue-name migration-orchestration-migration-requests-dlq --query QueueUrl --output text) \
    --attribute-names All \
    --message-attribute-names All

# 2. Parse message body
MESSAGE_BODY=$(aws sqs receive-message ... | jq '.Messages[0].Body')
echo $MESSAGE_BODY | jq .

# 3. Check schema validation
# Review migration_payload.json schema
cat lambdas/schemas/migration_payload.json

# 4. Check Lambda logs
CORRELATION_ID=$(echo $MESSAGE_BODY | jq -r '.correlationId')
aws logs filter-log-events \
    --log-group-name /aws/lambda/migration-orchestration-ingress-handler \
    --filter-pattern "{$.correlationId = \"$CORRELATION_ID\"}"
```

**Resolution**:

- **Invalid Schema**: Fix payload and resubmit
- **Missing Fields**: Add required fields and retry
- **Network Issue**: Check AWS service status, retry after 5 minutes
- **Quota Exceeded**: Request quota increase and retry

### Lambda Timeout

**Symptoms**: Lambda function takes > timeout seconds

**Investigation Steps**:

```bash
# 1. Check CloudWatch logs for duration
aws logs filter-log-events \
    --log-group-name /aws/lambda/migration-orchestration-prepare-source \
    --filter-pattern '"duration"'

# 2. Get Lambda metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value=migration-orchestration-prepare-source \
    --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Maximum,Average
```

**Resolution**:

- Increase timeout in `variables.tf`:
  ```hcl
  lambda_timeout = 600  # 10 minutes
  ```

- Optimize Lambda function performance
- Check network connectivity to external services
- Increase Lambda memory (more CPU allocated)

### Step Functions Stuck

**Symptoms**: Execution in progress for > expected time

**Investigation Steps**:

```bash
# 1. Get execution details
aws states describe-execution --execution-arn ARN

# 2. Get execution history
aws states get-execution-history --execution-arn ARN \
    --query 'events[?type==`TaskFailed`]'

# 3. Check Lambda role permissions
aws iam get-role-policy \
    --role-name migration-orchestration-lambda-execution-role \
    --policy-name migration-orchestration-lambda-sqs-policy
```

**Resolution**:

- **Lambda Role Issue**: Check IAM permissions
- **Timeout in Lambda**: Increase timeout
- **External Service Down**: Wait for service recovery
- **Stop Execution**: 
  ```bash
  aws states stop-execution \
      --execution-arn ARN \
      --cause "Manual stop for investigation"
  ```

### DynamoDB Throttling

**Symptoms**: DynamoDB throttle events in metrics

**Investigation Steps**:

```bash
# 1. Check throttle metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name UserErrors \
    --dimensions Name=TableName,Value=migration-orchestration-migration-state \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum

# 2. Get table capacity info
aws dynamodb describe-table \
    --table-name migration-orchestration-migration-state \
    --query 'Table.BillingModeSummary'
```

**Resolution**:

- Already using on-demand billing (auto-scaling)
- If provisioned, increase capacity:
  ```bash
  aws dynamodb update-table \
      --table-name migration-orchestration-migration-state \
      --billing-mode PAY_PER_REQUEST
  ```

### API Gateway Errors

**Symptoms**: 5xx errors from API endpoint

**Investigation Steps**:

```bash
# 1. Check API Gateway logs
aws logs filter-log-events \
    --log-group-name /aws/apigateway/migration-orchestration \
    --filter-pattern '{ $.status >= 500 }'

# 2. Check Lambda proxy function logs
aws logs tail /aws/lambda/migration-orchestration-ingress-handler-proxy --follow

# 3. Test endpoint directly
curl -X POST https://API_ID.execute-api.us-east-1.amazonaws.com/dev/migrations \
    -H "Content-Type: application/json" \
    -d '{"test":"payload"}' -v
```

**Resolution**:

- Check Lambda proxy function code
- Verify SQS queue is accessible
- Check Lambda role permissions
- Restart Lambda function if needed

## Maintenance Tasks

### Weekly

```bash
# Clean up old logs (keep 7 days)
for log_group in $(aws logs describe-log-groups --query 'logGroups[?starts_with(logGroupName, `/aws/migration`)].logGroupName' --output text); do
    aws logs put-retention-policy \
        --log-group-name $log_group \
        --retention-in-days 7
done

# Review CloudWatch dashboard
# Check for anomalies or trends

# Verify backups
aws dynamodb describe-backup \
    --table-name migration-orchestration-migration-state \
    --backup-arn $(aws dynamodb list-backups --table-name migration-orchestration-migration-state --query 'BackupSummaries[0].BackupArn' --output text)
```

### Monthly

```bash
# Review costs
aws ce list-cost-allocation-tags --query 'TagKeys[]' --output text

# Check IAM role usage
aws accessanalyzer validate-policy \
    --policy-document file://iam-policy.json \
    --policy-type IDENTITY_POLICY

# Update Lambda dependencies
cd lambdas
pip install --upgrade -r requirements.txt
git add requirements.txt && git commit -m "Update dependencies"

# Run security scan
pip install bandit
bandit -r . -f json > security-scan.json
```

### Quarterly

```bash
# Disaster recovery drill
# 1. Test DynamoDB restore
# 2. Test Terraform destroy/apply
# 3. Test Lambda function rollback
# 4. Test API endpoint functionality

# Review and update runbooks

# Security audit
aws iam access-advisor --entity-name migration-orchestration-lambda-execution-role

# Performance optimization review
# - Check Lambda memory utilization
# - Review DynamoDB access patterns
# - Audit EventBridge rules
```

## Troubleshooting Guide

### Problem: "Schema validation failed"

```bash
# 1. Check JSON payload format
jq . <<< '{"migrationId":"mig-123"}'

# 2. Validate against schema
python3 -m jsonschema lambdas/schemas/migration_payload.json -i payload.json

# 3. Common missing fields
# - migrationId (required)
# - appName (required)
# - source (required: azure|vmware|physical)
# - target (required: aws)
# - environment (required: dev|staging|prod)
# - wave (required: wave-N)
# - callbackUrl (required)
```

### Problem: "MGN not accessible"

```bash
# 1. Check MGN service status
aws mgn describe-source-servers --region us-east-1

# 2. Verify IAM permissions
aws iam get-user-policy --user-name USERNAME --policy-name PolicyName

# 3. Check region configuration
aws configure get region

# 4. Verify AWS account has MGN enabled
aws mgn describe-account-configuration
```

### Problem: "DynamoDB table not found"

```bash
# 1. Check table exists
aws dynamodb list-tables --query 'TableNames[]'

# 2. Check table name in environment
echo $DYNAMODB_TABLE
aws dynamodb describe-table --table-name $DYNAMODB_TABLE

# 3. Verify Lambda has permissions
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::ACCOUNT:role/lambda-role \
    --action-names dynamodb:GetItem \
    --resource-arns arn:aws:dynamodb:REGION:ACCOUNT:table/TABLE_NAME
```

### Problem: "Correlation ID not found"

```bash
# 1. Check correlation ID generation
grep -r "correlationId" lambdas/common/

# 2. Verify context propagation
grep -r "propagate_context" lambdas/

# 3. Trace through execution
aws states get-execution-history --execution-arn ARN \
    --query 'events[?type==`LambdaFunctionScheduled`]'
```

## Performance Tuning

### Lambda Memory Optimization

```bash
# Analyze memory usage
aws logs filter-log-events \
    --log-group-name /aws/lambda/migration-orchestration-FUNCTION \
    --filter-pattern '"Max Memory"' \
    --query 'events[].message' | jq -r '.[] | match("Max Memory.*") | .string'
```

### DynamoDB Query Optimization

```python
# Check query performance
import boto3
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('migration-orchestration-migration-state')

# Use GSI instead of scan
response = table.query(
    IndexName='wave-status-index',
    KeyConditionExpression='wave = :wave',
    ExpressionAttributeValues={':wave': 'wave-1'}
)
```

### SQS Batch Size Optimization

```hcl
# In lambda module, adjust batch size
resource "aws_lambda_event_source_mapping" "ingress_sqs" {
  batch_size = 25  # Increase for better throughput
}
```

## Alerts & Notifications

### Setting up SNS Notifications

```bash
# Create SNS topic
aws sns create-topic --name migration-alerts

# Subscribe email
aws sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:ACCOUNT:migration-alerts \
    --protocol email \
    --notification-endpoint admin@example.com

# Confirm subscription (check email)

# Add to CloudWatch alarm
aws cloudwatch put-metric-alarm \
    --alarm-name migration-dlq-alarm \
    --alarm-actions arn:aws:sns:us-east-1:ACCOUNT:migration-alerts
```

### Custom Metrics Alerts

```bash
# Create alarm for high replication lag
aws cloudwatch put-metric-alarm \
    --alarm-name replication-lag-high \
    --metric-name ReplicationLag \
    --namespace MigrationOrchestration \
    --statistic Average \
    --period 300 \
    --threshold 300 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2 \
    --alarm-actions arn:aws:sns:us-east-1:ACCOUNT:migration-alerts
```

## Scaling Considerations

### Handling 100+ Migrations

- **SQS**: Partition key ensures ordering
- **Lambda**: Auto-scales with SQS batch size
- **DynamoDB**: On-demand pricing = auto-scaling
- **Step Functions**: 25,000 concurrent state machines
- **EventBridge**: 10,000 events/second

### Performance Limits

| Component | Limit | Workaround |
|-----------|-------|-----------|
| Lambda timeout | 900s (15min) | Increase batch size or split work |
| SQS message size | 256KB | Use S3 for large payloads |
| DynamoDB item size | 400KB | Split large state objects |
| EventBridge rules | 100 per bus | Create multiple buses |
| Step Functions | 25,000 concurrent | Use standard vs express |

## Rollback Procedures

### Terraform Rollback

```bash
# 1. Keep previous state version
aws s3 ls s3://terraform-state/event-driven-migration/ --recursive

# 2. Revert to previous state
aws s3 cp s3://terraform-state/event-driven-migration/terraform.tfstate.backup \
    s3://terraform-state/event-driven-migration/terraform.tfstate

# 3. Apply with previous state
terraform apply -state=previous.tfstate

# 4. Verify resources
aws dynamodb list-tables
```

### Lambda Function Rollback

```bash
# 1. Get function version
aws lambda list-versions-by-function --function-name FUNCTION_NAME

# 2. Promote previous version to $LATEST
aws lambda update-alias \
    --function-name FUNCTION_NAME \
    --name LIVE \
    --function-version PREVIOUS_VERSION

# 3. Verify deployment
aws lambda invoke --function-name FUNCTION_NAME:LIVE response.json
```

### Database Rollback

```bash
# 1. Check point-in-time recovery window
aws dynamodb describe-table --table-name TABLE_NAME \
    --query 'Table.LatestRestorableDateTime'

# 2. Restore table
aws dynamodb restore-table-to-point-in-time \
    --source-table-name TABLE_NAME \
    --target-table-name TABLE_NAME-restore \
    --restore-date-time 2024-01-01T00:00:00Z

# 3. Validate restored data
aws dynamodb scan --table-name TABLE_NAME-restore --limit 10

# 4. Swap tables
# Update Lambda environment variable to new table name
```

## Support Contacts

- **AWS Support**: [AWS Support Console](https://console.aws.amazon.com/support/)
- **Platform Team**: platform@example.com
- **On-Call**: Check Pagerduty
- **Escalation**: Director of Engineering

## Additional Resources

- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Deployment guide
- [CloudWatch Dashboard](https://console.aws.amazon.com/cloudwatch/)
- [Step Functions Console](https://console.aws.amazon.com/states/)
- [MGN Console](https://console.aws.amazon.com/mgn/)
