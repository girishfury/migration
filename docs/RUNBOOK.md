# Operational Runbook

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Monitoring & Alerts](#monitoring--alerts)
3. [Incident Response](#incident-response)
4. [Troubleshooting](#troubleshooting)
5. [Common Issues & Solutions](#common-issues--solutions)
6. [Performance Tuning](#performance-tuning)
7. [Maintenance Tasks](#maintenance-tasks)

---

## Daily Operations

### 1. Health Check

**Frequency**: Every 2 hours or as part of scheduled monitoring

```bash
# Check CloudWatch dashboard
aws cloudwatch get-dashboard --dashboard-name migration-orchestration

# Check recent Lambda errors
aws logs filter-log-events \
  --log-group-name /aws/lambda \
  --start-time $(date -d '2 hours ago' +%s)000 \
  --filter-pattern "ERROR"

# Check SQS DLQ
aws sqs receive-message \
  --queue-url <DLQ_URL> \
  --max-number-of-messages 10
```

### 2. Queue Monitoring

**Check for stuck messages**:

```bash
# Get queue attributes
aws sqs get-queue-attributes \
  --queue-url <SQS_QUEUE_URL> \
  --attribute-names ApproximateNumberOfMessages \
  ApproximateNumberOfMessagesNotVisible \
  ApproximateNumberOfMessagesDelayed

# Expected values:
# - ApproximateNumberOfMessages: < 100
# - NotVisible: < 10 (processing)
# - Delayed: 0
```

### 3. Step Functions Execution Monitoring

**Check recent executions**:

```bash
# List recent executions
aws stepfunctions list-executions \
  --state-machine-arn <STATE_MACHINE_ARN> \
  --status-filter FAILED \
  --max-items 10

# Check specific execution
aws stepfunctions describe-execution \
  --execution-arn <EXECUTION_ARN>

# Get execution history
aws stepfunctions get-execution-history \
  --execution-arn <EXECUTION_ARN>
```

### 4. Migration Status Dashboard

**View active migrations**:

```bash
# Query DynamoDB for in-progress migrations
aws dynamodb scan \
  --table-name migration-state \
  --filter-expression "#s = :status" \
  --expression-attribute-names '{"#s":"status"}' \
  --expression-attribute-values '{":status":{"S":"MIGRATION_IN_PROGRESS"}}'
```

---

## Monitoring & Alerts

### CloudWatch Metrics

#### Key Metrics to Monitor

| Metric | Threshold | Action |
|--------|-----------|--------|
| DLQ Message Count | > 5 | Page on-call |
| Replication Lag | > 10 min | Warning |
| Lambda Error Rate | > 1% | Page on-call |
| Step Functions Failed Executions | > 2 per hour | Warning |
| EventBridge Failed Events | > 10 | Warning |

### Setting Up Alarms

```bash
# DLQ Alarm
aws cloudwatch put-metric-alarm \
  --alarm-name migration-dlq-alarm \
  --metric-name ApproximateNumberOfMessagesVisible \
  --namespace AWS/SQS \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions <SNS_TOPIC_ARN>

# Lambda Error Rate Alarm
aws cloudwatch put-metric-alarm \
  --alarm-name migration-lambda-errors \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions <SNS_TOPIC_ARN>
```

### Log Insights Queries

**Find recent errors**:

```
fields @timestamp, @message, @logStream, correlationId
| filter @message like /ERROR/
| stats count() by @logStream
```

**Track migration by ID**:

```
fields @timestamp, @message, @logStream
| filter correlationId = "mig-12345"
| sort @timestamp desc
```

**Replication lag analysis**:

```
fields @timestamp, replicationLag
| filter replicationLag > 300
| stats avg(replicationLag), max(replicationLag)
```

**Failed migrations**:

```
fields @timestamp, migrationId, errorCode, errorMessage
| filter status = "FAILED"
| stats count() by errorCode
```

---

## Incident Response

### Severity Levels

| Level | Response Time | Resolution Time | Escalation |
|-------|---------------|--------------------|------------|
| Critical (P1) | 15 min | 1 hour | VP Engineering |
| High (P2) | 30 min | 4 hours | Tech Lead |
| Medium (P3) | 2 hours | 8 hours | On-call Engineer |
| Low (P4) | 24 hours | 1 week | Backlog |

### Incident Triage

1. **Identify Severity**: Use table above
2. **Gather Information**:
   - Affected migrations (IDs)
   - Error messages
   - Execution history
   - Recent deployments
3. **Determine Root Cause**:
   - Check Lambda logs
   - Review Step Functions history
   - Verify AWS service status
   - Check EventBridge events
4. **Implement Fix**:
   - For code issues: Deploy hotfix
   - For configuration: Update parameters
   - For AWS limits: Request increase
5. **Verify Fix**: Rerun migration, monitor
6. **Post-Incident**: Document lessons learned

### Escalation Process

```
On-Call Engineer
    ↓ (P1: immediately, P2: 15 min, P3: 1 hour)
Tech Lead
    ↓ (if not resolved in 30 min)
VP Engineering
    ↓ (if production impact > 1 hour)
Executive Stakeholders
```

---

## Troubleshooting

### Lambda Function Issues

#### Lambda Timeout

**Symptoms**: `Task timed out after X.XX seconds`

**Investigation**:
```bash
# Check Lambda logs
aws logs tail /aws/lambda/<function-name> --follow

# Check Lambda configuration
aws lambda get-function-configuration --function-name <name>

# Check Lambda execution metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=<name>
```

**Solutions**:
1. Increase timeout: `aws lambda update-function-configuration --timeout 900`
2. Optimize code: Remove unnecessary operations
3. Increase memory: More memory = more CPU

#### Lambda OutOfMemory

**Symptoms**: `Process exited before completing request. Possible unhandled exception`

**Investigation**:
```bash
# Check memory configuration
aws lambda get-function-configuration --function-name <name> \
  --query 'MemorySize'

# Check memory usage metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name ConcurrentExecutions \
  --dimensions Name=FunctionName,Value=<name>
```

**Solutions**:
1. Increase memory: Allocate 512MB → 1024MB
2. Optimize code: Remove large objects
3. Use layers: External dependencies

#### Lambda Permissions Error

**Symptoms**: `User: arn:aws:iam::... is not authorized to perform: ...`

**Investigation**:
```bash
# Check Lambda execution role
aws lambda get-function --function-name <name> \
  --query 'Configuration.Role'

# Check role policies
aws iam list-role-policies --role-name <role-name>
aws iam get-role-policy --role-name <role-name> --policy-name <policy>
```

**Solutions**:
1. Add missing permissions to IAM role
2. Verify resource ARNs in policies
3. Check KMS key permissions for encryption

### EventBridge Issues

#### Events Not Being Delivered

**Symptoms**: Events published but no Lambda invocation

**Investigation**:
```bash
# Check EventBridge rules
aws events list-rules --event-bus-name custom-migration-bus

# Check rule targets
aws events list-targets-by-rule \
  --rule migration-requested \
  --event-bus-name custom-migration-bus

# Check CloudWatch event history
aws events start-replay \
  --event-source-arn <source-arn> \
  --event-time-start 2024-01-01T00:00:00Z
```

**Solutions**:
1. Verify event bus name in publisher code
2. Check rule patterns match event structure
3. Verify target Lambda has EventBridge invoke permission
4. Enable rule: `aws events enable-rule --name <rule-name>`

#### Dead Letter Queue (DLQ)

**Check DLQ messages**:

```bash
aws sqs receive-message \
  --queue-url <DLQ_URL> \
  --max-number-of-messages 10 \
  --wait-time-seconds 20

# Replay DLQ messages
aws sqs send-message \
  --queue-url <MAIN_QUEUE_URL> \
  --message-body <message-from-dlq>
```

### DynamoDB Issues

#### Table Throttling

**Symptoms**: `ProvisionedThroughputExceededException`

**Investigation**:
```bash
# Check table capacity
aws dynamodb describe-table --table-name migration-state \
  --query 'Table.[BillingModeSummary,ProvisionedThroughput]'

# Check metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=migration-state \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Maximum
```

**Solutions**:
1. Switch to on-demand billing
2. Increase provisioned capacity
3. Optimize queries to use GSI
4. Implement exponential backoff retry

#### Item Size Exceeded

**Symptoms**: `One or more parameter values were invalid: An AttributeValue may not contain an empty string`

**Investigation**:
```bash
# Calculate item size
aws dynamodb query --table-name migration-state \
  --key-condition-expression "migrationId = :id" \
  --expression-attribute-values '{":id":{"S":"mig-12345"}}' \
  --return-consumed-capacity TOTAL
```

**Solutions**:
1. Reduce execution details stored in item
2. Move large data to S3 and store reference
3. Archive old migrations to separate table

### Step Functions Issues

#### Execution Failed

**Investigation**:
```bash
# Describe failed execution
aws stepfunctions describe-execution \
  --execution-arn <ARN> \
  --query '[startDate,stopDate,status,cause,error]'

# Get full history
aws stepfunctions get-execution-history \
  --execution-arn <ARN> \
  --query 'events' | jq '.[] | select(.type=="ExecutionFailed")'
```

**Solutions**:
1. Review Lambda function logs
2. Check state machine definition for errors
3. Verify task timeout values
4. Manually retry execution if safe

#### State Machine Stuck

**Investigation**:
```bash
# List running executions
aws stepfunctions list-executions \
  --state-machine-arn <ARN> \
  --status-filter RUNNING \
  --max-items 100

# Check execution progress
aws stepfunctions get-execution-history \
  --execution-arn <ARN> \
  --query 'events[-5:]'  # Last 5 events
```

**Solutions**:
1. Check Lambda function still running
2. Increase state machine timeout
3. Stop execution if necessary: `aws stepfunctions stop-execution`
4. Review recent Lambda changes

### MGN Integration Issues

#### No Source Servers Found

**Investigation**:
```bash
# Check MGN servers
aws mgn describe-source-servers \
  --query 'items[*].[sourceServerID,status]'

# Check MGN service status
aws mgn get-launch-configuration \
  --source-server-id <id>
```

**Solutions**:
1. Verify MGN is initialized in region
2. Install MGN replication agent on source
3. Check network connectivity to MGN endpoint
4. Verify source server ID matches

#### Replication Lag Too High

**Investigation**:
```bash
# Check replication status
aws mgn describe-source-servers \
  --query 'items[*].[sourceServerID,replicationStatus.replicationLagSec]'

# Monitor over time
for i in {1..5}; do
  aws mgn describe-source-servers --query 'items[0].replicationStatus.replicationLagSec'
  sleep 60
done
```

**Solutions**:
1. Increase network bandwidth
2. Reduce source I/O load
3. Scale MGN infrastructure
4. Check for network latency

---

## Common Issues & Solutions

### Migration Stuck in MIGRATION_IN_PROGRESS

**Root Cause**: Verify Lambda timeout or MGN API hanging

**Resolution**:
1. Check `/aws/lambda/verify-migration` logs
2. Run manual MGN status check
3. Increase polling timeout in Step Functions
4. Restart verification step

### Replication Failed with Network Error

**Root Cause**: Network connectivity issues

**Resolution**:
```bash
# Verify network connectivity
ping <mgn-endpoint>
aws ec2 describe-security-groups \
  --filter "Name=group-name,Values=mgn-*"

# Check VPC endpoints
aws ec2 describe-vpc-endpoints \
  --filters "Name=service-name,Values=*mgn*"
```

### CMDB Update Failed

**Root Cause**: CMF API authentication or timeout

**Resolution**:
1. Verify CMF API credentials in Secrets Manager
2. Check CMF service availability
3. Increase timeout in finalize_cutover Lambda
4. Review CMF API documentation

### Callback URL Unreachable

**Root Cause**: Network or DNS issue

**Resolution**:
1. Verify callback URL format
2. Check DNS resolution: `nslookup <domain>`
3. Test connectivity: `curl -v <callback-url>`
4. Check firewall rules
5. Update callback URL if changed

### Rollback Failed

**Root Cause**: Source already decommissioned or AWS limit

**Resolution**:
1. Check if source VM still exists
2. Verify IAM permissions for termination
3. Check AWS service limits
4. Manually restore from backup if needed

---

## Performance Tuning

### Lambda Optimization

**Memory Allocation**:
```bash
# Run CloudWatch metrics for duration by memory
aws lambda list-functions --query 'Functions[*].[FunctionName,MemorySize]'

# Recommend: 3x baseline memory for optimal cost/performance
```

**Concurrency Control**:
```bash
# Set reserved concurrency (prevent throttling)
aws lambda put-function-concurrency \
  --function-name validate-input \
  --reserved-concurrent-executions 100

# Set provisioned concurrency (warm starts)
aws lambda put-provisioned-concurrency-config \
  --function-name ingress-handler \
  --provisioned-concurrent-executions 10
```

### Step Functions Optimization

**Reduce State Transitions**:
- Use parallel execution where applicable
- Combine small tasks into one Lambda
- Use direct service integration (EventBridge → Lambda)

**Timeout Configuration**:
- Set reasonable timeouts to catch hangs early
- Use exponential backoff for retries
- Implement jitter to prevent thundering herd

### DynamoDB Optimization

**Query Patterns**:
```bash
# Analyze query performance
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --statistics Average,Maximum

# Review GSI usage
aws dynamodb describe-table --table-name migration-state \
  --query 'Table.GlobalSecondaryIndexes[*].[IndexName,IndexStatus]'
```

**TTL Configuration**:
```bash
# Set TTL for automatic cleanup (30 days)
aws dynamodb update-time-to-live \
  --table-name migration-state \
  --time-to-live-specification 'AttributeName=ttl,Enabled=true'
```

---

## Maintenance Tasks

### Weekly Tasks

1. **Review CloudWatch Dashboards**
   - Check migration success rate
   - Monitor error trends
   - Review cost utilization

2. **Update Dependencies**
   ```bash
   # Check for updates
   pip list --outdated
   
   # Update in requirements.txt
   pip install --upgrade boto3 requests jsonschema
   ```

3. **Backup State**
   ```bash
   # Export DynamoDB data
   aws dynamodb scan --table-name migration-state > backup.json
   
   # Archive to S3
   aws s3 cp backup.json s3://migration-backups/
   ```

### Monthly Tasks

1. **Security Audit**
   - Review IAM role permissions
   - Audit Lambda environment variables
   - Check KMS key rotation
   - Review Secrets Manager secrets

2. **Performance Review**
   ```bash
   # Analyze metrics
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Duration \
     --start-time $(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 86400 \
     --statistics Average,Maximum
   ```

3. **Cost Optimization**
   - Review Lambda execution patterns
   - Check for unused resources
   - Optimize DynamoDB capacity
   - Review data transfer costs

### Quarterly Tasks

1. **Disaster Recovery Drill**
   - Test failover procedures
   - Verify backup restoration
   - Check documentation accuracy
   - Update runbooks as needed

2. **Capacity Planning**
   - Review growth trends
   - Project future requirements
   - Plan infrastructure upgrades
   - Update SLAs if needed

3. **Security Assessment**
   - Run vulnerability scans
   - Update Lambda runtimes
   - Audit dependencies
   - Review compliance requirements

### Annual Tasks

1. **Complete Audit**
   - Security assessment
   - Cost optimization review
   - Architecture review
   - Vendor assessment

2. **Documentation Update**
   - Update all runbooks
   - Revise architecture diagrams
   - Update deployment procedures
   - Review disaster recovery plans

3. **Team Training**
   - Incident response drills
   - Troubleshooting workshops
   - Architecture reviews
   - Best practices updates

---

## Contact & Escalation

### On-Call Rotation

- **Primary**: [Name] - [Contact]
- **Secondary**: [Name] - [Contact]
- **Manager**: [Name] - [Contact]

### Escalation Contacts

- **AWS Support**: [Account ID] - [Support Tier]
- **CMF Support**: [Contact Info]
- **MGN Support**: [Contact Info]

### Status Page

- **Internal**: [Link]
- **Public**: [Link]
- **Incident Channel**: [Slack Channel]

---

## Related Documentation

- [README.md](./README.md) - Installation & usage
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System design
- [GitHub Issues](https://github.com/...) - Bug tracking
- [Terraform Docs](../terraform/README.md) - Infrastructure
