# Event-Driven Migration Orchestration Framework

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org)
[![Terraform 1.5.0+](https://img.shields.io/badge/Terraform-1.5.0%2B-blue)](https://www.terraform.io)
[![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-FF9900)](https://aws.amazon.com/lambda)
[![EventBridge](https://img.shields.io/badge/AWS-EventBridge-FF9900)](https://aws.amazon.com/eventbridge)

A production-ready, event-driven migration orchestration framework for migrating 100+ VMs from Azure to AWS using AWS MGN (Application Migration Service), Cloud Migration Factory, GitHub Actions, and AWS serverless services.

## Quick Start

### Prerequisites

- AWS Account with MGN enabled
- GitHub repository with OIDC configured
- Terraform >= 1.5.0
- Python 3.11+
- AWS CLI v2
- Git

### 1. Clone & Setup

```bash
# Clone repository
git clone <repository-url>
cd migration

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r lambdas/requirements.txt
```

### 2. Configure AWS

```bash
# Configure AWS CLI
aws configure

# Set environment variables
export AWS_REGION="us-east-1"
export TF_VAR_project_name="migration-orchestration"
export TF_VAR_environment="dev"
```

### 3. Initialize Terraform

```bash
cd terraform

# Initialize Terraform
terraform init \
  -backend-config="bucket=your-state-bucket" \
  -backend-config="region=us-east-1"

# Validate configuration
terraform validate
```

### 4. Deploy Infrastructure

```bash
# Plan deployment
terraform plan -out=tfplan

# Apply deployment
terraform apply tfplan

# Get outputs
terraform output
```

### 5. Trigger Migration

```bash
# Send migration request to SQS
aws sqs send-message \
  --queue-url $(terraform output -raw sqs_queue_url) \
  --message-body '{
    "migrationId": "mig-12345",
    "appName": "billing-app",
    "source": "azure",
    "target": "aws",
    "environment": "prod",
    "wave": "wave-3",
    "sourceVmId": "vm-123456",
    "targetVmName": "billing-app-prod-01",
    "instanceType": "t3.large",
    "subnetId": "subnet-12345",
    "securityGroupIds": ["sg-12345"]
  }'

# Monitor execution
aws stepfunctions describe-execution \
  --execution-arn $(aws stepfunctions list-executions \
    --state-machine-arn $(terraform output -raw state_machine_arn) \
    --max-items 1 --query 'executions[0].executionArn' \
    --output text)
```

## Architecture Overview

```
GitHub Actions (CI/CD)
    ↓
SQS Queue → Ingress Lambda
    ↓
EventBridge Custom Bus
    ↓
Step Functions State Machine
    ├── Validate Input
    ├── Prepare Source
    ├── Trigger Migration
    ├── Verify Migration (with polling)
    ├── Finalize Cutover
    └── Rollback (on failure)
    ↓
AWS MGN / CMF / AWS Services
    ↓
External Systems (Callbacks)
```

## Project Structure

```
migration/
├── lambdas/                          # Lambda function source code
│   ├── common/                       # Shared utilities
│   │   ├── logger.py                # Structured logging
│   │   ├── correlation.py           # Correlation ID management
│   │   ├── errors.py                # Custom exceptions
│   │   ├── dynamodb_helper.py       # DynamoDB operations
│   │   └── eventbridge_helper.py    # EventBridge operations
│   ├── schemas/                      # JSON schemas
│   │   └── migration_payload.json   # Validation schema
│   ├── tests/                        # Unit tests
│   │   ├── test_ingress_handler.py
│   │   ├── test_validate_input.py
│   │   └── test_common.py
│   ├── ingress_handler.py           # SQS → EventBridge
│   ├── validate_input.py            # Validate prerequisites
│   ├── prepare_source.py            # Prepare source VM
│   ├── trigger_migration.py         # Trigger MGN
│   ├── verify_migration.py          # Verify status
│   ├── finalize_cutover.py          # Complete migration
│   ├── callback_handler.py          # Send callbacks
│   ├── rollback_handler.py          # Handle failures
│   └── requirements.txt             # Python dependencies
├── terraform/                        # Infrastructure as Code
│   ├── main.tf                      # Provider configuration
│   ├── variables.tf                 # Input variables
│   ├── outputs.tf                   # Output values
│   ├── environments/                # Environment configs
│   │   ├── dev.tfvars
│   │   └── prod.tfvars
│   └── modules/                     # Terraform modules
│       ├── sqs.tf
│       ├── eventbridge.tf
│       ├── dynamodb.tf
│       ├── iam.tf
│       ├── lambda.tf
│       ├── stepfunctions.tf
│       ├── kms.tf
│       └── api-gateway.tf
├── .github/workflows/               # CI/CD pipelines
│   └── deploy.yml                  # GitHub Actions workflow
├── docs/                            # Documentation
│   ├── README.md                   # Full documentation
│   ├── ARCHITECTURE.md             # Architecture details
│   └── RUNBOOK.md                  # Operational runbook
└── README.md                        # This file
```

## Lambda Functions

| Function | Purpose | Input | Output |
|----------|---------|-------|--------|
| `ingress_handler` | Receive SQS messages | SQS Event | MigrationRequested |
| `validate_input` | Validate prerequisites | EventBridge Event | MigrationStatusUpdated |
| `prepare_source` | Prepare source VM | EventBridge Event | Status Event |
| `trigger_migration` | Start MGN migration | EventBridge Event | Progress Event |
| `verify_migration` | Monitor replication | EventBridge Event | Verification Event |
| `finalize_cutover` | Complete migration | EventBridge Event | Success Event |
| `callback_handler` | Send status callbacks | Any Status Event | HTTP POST |
| `rollback_handler` | Handle failures | Failure Event | Rollback Event |

## Key Features

✅ **Event-Driven Architecture**: All components communicate via EventBridge  
✅ **Stateless Execution**: Lambda functions are stateless and scalable  
✅ **Stateful Orchestration**: Step Functions manages complex workflows  
✅ **Fully Automated**: End-to-end automation via GitHub Actions  
✅ **Extensible Design**: Modular approach for future enhancements  
✅ **Production-Ready**: Security, observability, and error handling included  
✅ **Scalable**: Handles 100+ concurrent migrations  
✅ **Reliable**: Retry logic, error handling, and rollback capabilities  
✅ **Observable**: CloudWatch, X-Ray, and structured logging  
✅ **Secure**: KMS encryption, IAM least privilege, OIDC auth  

## Security Considerations

### Authentication & Authorization
- GitHub OIDC for secure CI/CD authentication
- IAM roles with least privilege permissions
- Service-specific execution roles
- No hardcoded credentials

### Encryption
- KMS keys for data at rest (SQS, DynamoDB, Lambda env vars)
- TLS 1.2+ for data in transit
- Secrets Manager for sensitive data

### Network
- VPC endpoints for AWS service access
- Security groups for traffic control
- Optional private subnet deployment

### Compliance
- Audit logging via CloudTrail
- Access logging for all API calls
- Data retention policies
- Encryption key rotation

## Testing

### Unit Tests

```bash
cd lambdas
pytest tests/ -v --cov=.
```

### Integration Tests

```bash
cd tests
pytest integration/ -v
```

### Manual Testing

```bash
# Trigger test migration
aws sqs send-message --queue-url <URL> --message-body '...'

# Monitor execution
aws stepfunctions describe-execution --execution-arn <ARN>

# Check logs
aws logs tail /aws/lambda/ingress-handler --follow
```

## Monitoring & Alerts

### CloudWatch Dashboard

Pre-built dashboard includes:
- Migration success rate
- Average migration duration
- Error rate by type
- Replication lag metrics
- DLQ message count

### Key Metrics

| Metric | Alert Threshold |
|--------|-----------------|
| DLQ Messages | > 5 |
| Error Rate | > 1% |
| Replication Lag | > 10 min |
| Step Functions Failures | > 2/hour |

### Viewing Logs

```bash
# Tail recent logs
aws logs tail /aws/lambda/ingress-handler --follow

# Filter by correlation ID
aws logs filter-log-events \
  --log-group-name /aws/lambda \
  --filter-pattern "correlation_id"

# Get error summary
aws logs insights \
  --log-group-name /aws/lambda \
  --query 'fields @message | filter @message like /ERROR/'
```

## Cost Optimization

### Estimated Monthly Costs (100 migrations/month)

| Service | Usage | Cost |
|---------|-------|------|
| Lambda | ~500k invocations | ~$10 |
| SQS | ~100k messages | ~$0.20 |
| DynamoDB | ~10GB reads/writes | ~$50 |
| EventBridge | ~1M events | ~$0.50 |
| Step Functions | ~500 executions | ~$5 |
| **Total** | | **~$65** |

### Cost Reduction Tips

1. Use DynamoDB on-demand for variable workloads
2. Enable Lambda reserved concurrency to reduce cold starts
3. Implement TTL on DynamoDB for automatic cleanup
4. Use S3 for large execution details
5. Consolidate Lambda functions where possible

## Troubleshooting

### Migration Stuck

```bash
# Check Step Functions execution
aws stepfunctions get-execution-history --execution-arn <ARN>

# Check Lambda logs
aws logs tail /aws/lambda/<function> --follow

# Check MGN status
aws mgn describe-source-servers
```

### High Replication Lag

```bash
# Monitor replication lag
aws mgn describe-source-servers \
  --query 'items[*].[sourceServerID,replicationStatus.replicationLagSec]'

# Check network bandwidth
# Check source I/O load
# Scale MGN infrastructure if needed
```

### Callback Failures

```bash
# Check callback logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/callback-handler \
  --filter-pattern "CALLBACK_FAILED"

# Verify callback URL
curl -v <callback-url>

# Check network connectivity
ping <callback-domain>
```

## Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Make changes and test: `pytest tests/`
4. Commit changes: `git commit -am 'Add new feature'`
5. Push to branch: `git push origin feature/new-feature`
6. Submit pull request

## Changelog

### v1.0.0 (2024-01-XX)
- Initial release
- 8 Lambda functions
- Step Functions state machine
- EventBridge integration
- GitHub Actions CI/CD
- Comprehensive documentation

## Support

For issues or questions:
1. Check [RUNBOOK.md](docs/RUNBOOK.md) for troubleshooting
2. Review [ARCHITECTURE.md](docs/ARCHITECTURE.md) for design details
3. Open GitHub issue with details
4. Contact on-call engineer

## License

[Your License Here]

## Additional Resources

- [AWS MGN Documentation](https://docs.aws.amazon.com/mgn/)
- [AWS Step Functions](https://docs.aws.amazon.com/step-functions/)
- [EventBridge](https://docs.aws.amazon.com/eventbridge/)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

---

## Quick Reference

### Environment Variables

```bash
AWS_REGION              # AWS region (default: us-east-1)
EVENTBRIDGE_BUS_NAME    # EventBridge custom bus name
DYNAMODB_TABLE_NAME     # DynamoDB table for state
SQS_QUEUE_URL          # SQS queue URL for requests
MGN_REGION             # AWS MGN region
DEBUG                  # Enable debug logging (true/false)
```

### Important URLs

- [AWS Console](https://console.aws.amazon.com)
- [Step Functions](https://console.aws.amazon.com/states)
- [Lambda Functions](https://console.aws.amazon.com/lambda/home)
- [DynamoDB Tables](https://console.aws.amazon.com/dynamodb)
- [EventBridge](https://console.aws.amazon.com/events)

### Common Commands

```bash
# Deploy
cd terraform && terraform apply

# Test
cd lambdas && pytest tests/ -v

# Monitor
aws logs tail /aws/lambda --follow

# Rollback
cd terraform && terraform destroy

# View state
aws dynamodb scan --table-name migration-state

# Check queue
aws sqs get-queue-attributes --queue-url <URL>
```

---

**Last Updated**: 2024-01-XX  
**Maintained By**: [Your Team]  
**Status**: Production Ready ✅
