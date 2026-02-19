# Migration Orchestration Framework

## Overview

This is a production-ready, event-driven migration orchestration framework designed to migrate 100+ VMs from Azure to AWS using AWS MGN (Application Migration Service), Cloud Migration Factory, GitHub Actions, and AWS serverless services.

## Architecture

### Core Principles

- **Event-Driven**: All components communicate via EventBridge
- **Stateless Execution**: Lambda functions are stateless
- **Stateful Orchestration**: Step Functions manages workflow state
- **Fully Automated**: End-to-end automation via GitHub Actions
- **Extensible**: Modular design for future enhancements
- **Production-Ready**: Security, observability, and error handling built-in

### System Architecture

```
GitHub Action / API
        ↓
    SQS Queue
        ↓
Ingress Lambda
        ↓
  EventBridge
        ↓
  Step Functions
        ↓
Lambda Functions (Validation, Preparation, Triggering, Verification, Cutover, Rollback)
        ↓
AWS MGN / CMF / AWS Services
        ↓
Callback Lambda
        ↓
External Systems
```

## Directory Structure

```
migration/
├── lambdas/
│   ├── common/
│   │   ├── __init__.py
│   │   ├── logger.py              # Structured logging with correlation IDs
│   │   ├── correlation.py         # Correlation ID management
│   │   ├── errors.py              # Custom exception types
│   │   ├── dynamodb_helper.py     # DynamoDB state management
│   │   └── eventbridge_helper.py  # EventBridge event publishing
│   ├── schemas/
│   │   └── migration_payload.json # JSON schema for validation
│   ├── tests/
│   │   ├── test_ingress_handler.py
│   │   ├── test_validate_input.py
│   │   └── test_common.py
│   ├── ingress_handler.py         # Receives SQS messages, publishes to EventBridge
│   ├── validate_input.py          # Validates prerequisites
│   ├── prepare_source.py          # Prepares source VM
│   ├── trigger_migration.py       # Triggers MGN migration
│   ├── verify_migration.py        # Verifies migration status
│   ├── finalize_cutover.py        # Finalizes cutover
│   ├── callback_handler.py        # Sends status callbacks
│   ├── rollback_handler.py        # Handles rollback
│   └── requirements.txt           # Python dependencies
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── sqs.tf
│       ├── eventbridge.tf
│       ├── dynamodb.tf
│       ├── iam.tf
│       ├── lambda.tf
│       ├── stepfunctions.tf
│       ├── kms.tf
│       └── api-gateway.tf
├── .github/
│   └── workflows/
│       └── deploy.yml            # CI/CD pipeline
├── docs/
│   ├── ARCHITECTURE.md           # Detailed architecture
│   ├── RUNBOOK.md               # Operational runbook
│   └── README.md                # This file
└── requirements.txt             # Project-wide dependencies
```

## Lambda Functions

### 1. Ingress Handler (`ingress_handler.py`)

Receives SQS messages containing migration requests, validates schema, and publishes to EventBridge.

**Input**: SQS message with migration payload

**Output**: Publishes `MigrationRequested` event to EventBridge

**Error Handling**: Failed messages go to DLQ

### 2. Validate Input (`validate_input.py`)

Validates migration payload, checks AWS prerequisites, and verifies connectivity.

**Input**: `MigrationRequested` event from EventBridge

**Output**: Publishes `MigrationStatusUpdated` event

**Prerequisites Checked**:
- AWS resources exist (subnets, security groups)
- MGN service is available
- CMF integration is ready

### 3. Prepare Source (`prepare_source.py`)

Prepares the source VM for migration by installing agents and creating snapshots.

**Input**: Validated migration event

**Output**: Publishes status update event

**Actions**:
- Installs MGN agent on source
- Creates snapshots
- Validates source readiness

### 4. Trigger Migration (`trigger_migration.py`)

Calls AWS MGN API to start migration (test or cutover phase).

**Input**: Prepared source event

**Output**: Publishes migration progress event

**Actions**:
- Triggers MGN test launch or cutover
- Updates CMF wave status
- Records job ID for tracking

### 5. Verify Migration (`verify_migration.py`)

Polls MGN status, validates replication lag, and checks application health.

**Input**: Migration in-progress event

**Output**: Publishes verification result event

**Verifications**:
- Replication lag < 5 minutes (configurable)
- Application health checks pass
- Target instance is responsive

### 6. Finalize Cutover (`finalize_cutover.py`)

Performs final cutover steps including DNS updates and source decommission.

**Input**: Verified migration event

**Output**: Publishes `MigrationSucceeded` event

**Actions**:
- Updates DNS records
- Decommissions source VM
- Updates CMDB
- Archives migration metadata

### 7. Callback Handler (`callback_handler.py`)

Sends migration status to callback URLs provided by external systems.

**Input**: Any migration status event

**Output**: HTTP POST to callback URL

**Retry Policy**: Exponential backoff (max 3 retries)

### 8. Rollback Handler (`rollback_handler.py`)

Handles rollback on failure, restores previous state, and notifies stakeholders.

**Input**: Failure event from Step Functions

**Output**: Publishes `MigrationRolledBack` event

**Actions**:
- Stops MGN replication
- Terminates target instance
- Restores source VM state
- Sends notifications

## Deployment Prerequisites

### AWS Account Requirements

- AWS MGN enabled in target region
- Cloud Migration Factory configured
- DynamoDB, Lambda, EventBridge, SQS, KMS services available
- Appropriate IAM permissions

### GitHub Configuration

- Repository with OIDC provider configured
- GitHub Actions enabled
- Secrets configured: `AWS_ROLE_TO_ASSUME`

### Local Requirements

- Terraform >= 1.5.0
- Python 3.11+
- AWS CLI v2
- Git

## Installation & Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd migration
```

### 2. Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter your default region
# Enter your default output format (json)
```

### 3. Install Python Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r lambdas/requirements.txt
```

### 4. Initialize Terraform

```bash
cd terraform
terraform init -backend-config="bucket=your-state-bucket"
```

## Configuration

### Environment Variables

Create `terraform/terraform.tfvars`:

```hcl
environment    = "dev"
region         = "us-east-1"
project_name   = "migration-orchestration"
```

### Lambda Configuration

Lambda functions use environment variables:

- `EVENTBRIDGE_BUS_NAME`: Custom EventBridge bus name
- `DYNAMODB_TABLE_NAME`: Migration state table
- `SQS_QUEUE_URL`: Migration request queue
- `MGN_REGION`: AWS region for MGN
- `CMF_API_ENDPOINT`: Cloud Migration Factory API endpoint

## Deployment

### Development Environment

```bash
# Validate Terraform
cd terraform
terraform validate

# Plan deployment
terraform plan -out=tfplan

# Apply deployment
terraform apply tfplan

# Deploy Lambda functions via GitHub Actions
git push origin develop
```

### Production Environment

```bash
# Requires manual approval
git push origin main

# Approve deployment in GitHub Actions UI
# Deployment will proceed with production settings
```

## Message Payload Standard

All components use this canonical format:

```json
{
  "migrationId": "mig-12345",
  "appName": "billing-app",
  "source": "azure",
  "target": "aws",
  "environment": "prod",
  "wave": "wave-3",
  "steps": ["freeze", "replicate", "validate", "switch"],
  "callbackUrl": "https://runbook/status",
  "sourceVmId": "vm-123456",
  "targetVmName": "billing-app-prod-01",
  "instanceType": "t3.large",
  "subnetId": "subnet-12345",
  "securityGroupIds": ["sg-12345"],
  "tags": {
    "Environment": "prod",
    "Application": "billing"
  }
}
```

## Testing

### Unit Tests

```bash
cd lambdas
pytest tests/ -v
```

### Integration Tests

```bash
# Deploy to dev environment first
cd tests
pytest integration/ -v
```

### Manual Testing

1. **Trigger Test Migration**:
```bash
aws sqs send-message \
  --queue-url <SQS_QUEUE_URL> \
  --message-body '{...migration payload...}'
```

2. **Monitor Execution**:
   - Check Step Functions console for execution status
   - Review CloudWatch logs for each Lambda
   - Verify EventBridge events in CloudWatch Events

3. **Check MGN Integration**:
   - Confirm MGN API calls in CloudTrail
   - Check MGN console for replication status
   - Verify CMF wave updates

## Security Considerations

### Encryption

- **At Rest**: KMS keys for SQS, DynamoDB, Lambda env vars
- **In Transit**: TLS 1.2+ for all API calls
- **Secrets**: AWS Secrets Manager for sensitive data

### IAM

- Least privilege IAM roles and policies
- Scoped Lambda execution roles
- Service-specific permissions

### GitHub OIDC

GitHub OIDC trust relationship must be configured before deployment:

```bash
aws iam create-role \
  --role-name github-actions-role \
  --assume-role-policy-document file://trust-policy.json
```

## Observability

### CloudWatch

- **Logs**: Structured JSON logging with correlation IDs
- **Metrics**: Custom metrics for success/failure rates
- **Alarms**: DLQ monitoring and execution failures

### X-Ray

- End-to-end request tracing
- Service map visualization
- Performance analysis

### Step Functions Logging

Full execution history with detailed state information.

## Troubleshooting

### Common Issues

1. **Migration stuck in progress**
   - Check Lambda CloudWatch logs for errors
   - Verify MGN status in AWS console
   - Check Step Functions execution history

2. **Validation failures**
   - Verify SQS message format matches schema
   - Check AWS resource prerequisites
   - Review validation Lambda logs

3. **Rollback failures**
   - Check if target instance exists
   - Verify source VM can be restored
   - Review rollback Lambda logs

### Debug Mode

Enable debug logging:

```bash
aws logs create-log-group --log-group-name /aws/lambda/debug
export DEBUG=true
terraform apply
```

## Monitoring & Alerts

### Key Metrics

- Migration success rate
- Average migration time
- Replication lag
- DLQ message count
- Step Functions execution duration

### Alert Thresholds

- DLQ messages > 5: Page on-call
- Replication lag > 10 minutes: Warning
- Migration failure: Page on-call
- Execution timeout: Page on-call

## Maintenance

### Regular Tasks

- Review and update Lambda dependencies monthly
- Rotate AWS credentials (if using IAM keys)
- Review and optimize costs
- Update Terraform modules

### Backup & Disaster Recovery

- DynamoDB point-in-time recovery enabled
- S3 state file versioning enabled
- Cross-region failover plan in place

## Support & Contribution

For issues, feature requests, or contributions:

1. Create an issue in the GitHub repository
2. Include reproduction steps
3. Attach relevant logs
4. Submit pull request for review

## License

[Your License Here]

## Additional Resources

- [AWS MGN Documentation](https://docs.aws.amazon.com/mgn/)
- [AWS Step Functions Documentation](https://docs.aws.amazon.com/step-functions/)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [EventBridge Documentation](https://docs.aws.amazon.com/eventbridge/)
