# Deployment Checklist

Use this checklist to ensure all prerequisites are met before deploying the migration orchestration framework.

## Pre-Deployment Phase

### AWS Account Setup
- [ ] AWS Account created and verified
- [ ] AWS CLI v2 installed and configured
- [ ] AWS credentials configured (`aws configure`)
- [ ] Default region set (e.g., us-east-1)
- [ ] Account has necessary permissions for:
  - [ ] EC2 (for security group/subnet management)
  - [ ] MGN (Application Migration Service)
  - [ ] Lambda (function creation/management)
  - [ ] DynamoDB (table creation)
  - [ ] EventBridge (event bus management)
  - [ ] SQS (queue creation)
  - [ ] IAM (role/policy management)
  - [ ] KMS (key creation)
  - [ ] S3 (state file storage)

### GitHub Setup
- [ ] GitHub repository created
- [ ] GitHub repository cloned locally
- [ ] GitHub organization configured (if applicable)
- [ ] OIDC provider configured in AWS:
  ```bash
  # AWS Console → IAM → Identity providers
  # Provider type: OpenID Connect
  # Provider URL: https://token.actions.githubusercontent.com
  # Audience: sts.amazonaws.com
  ```
- [ ] IAM role created for GitHub Actions
- [ ] Trust policy configured for GitHub repository
- [ ] GitHub Actions enabled in repository settings

### Local Environment
- [ ] Python 3.11+ installed
  ```bash
  python --version  # Should be 3.11+
  ```
- [ ] Terraform >= 1.5.0 installed
  ```bash
  terraform version  # Should be 1.5.0+
  ```
- [ ] Git installed and configured
  ```bash
  git config --global user.name "Your Name"
  git config --global user.email "your@email.com"
  ```
- [ ] Virtual environment created
  ```bash
  python -m venv venv
  source venv/bin/activate
  ```
- [ ] Python dependencies installed
  ```bash
  pip install -r lambdas/requirements.txt
  ```

### AWS Infrastructure Prerequisites
- [ ] S3 bucket created for Terraform state
  ```bash
  aws s3api create-bucket --bucket migration-terraform-state --region us-east-1
  aws s3api put-bucket-versioning --bucket migration-terraform-state --versioning-configuration Status=Enabled
  aws s3api put-bucket-encryption --bucket migration-terraform-state --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
  ```
- [ ] S3 bucket block public access configured
  ```bash
  aws s3api put-public-access-block --bucket migration-terraform-state --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
  ```
- [ ] MGN service enabled and initialized in target region
- [ ] Cloud Migration Factory (CMF) deployed and configured
- [ ] VPC and subnets created (if using VPC deployment)
- [ ] Security groups created/identified for Lambda
- [ ] KMS keys created (or IAM permissions for creation)

---

## Repository Setup Phase

### Clone & Configure
- [ ] Repository cloned to local machine
- [ ] Branch protection rules configured (main branch):
  - [ ] Require pull request reviews
  - [ ] Dismiss stale pull request approvals
  - [ ] Require status checks to pass
  - [ ] Require branches to be up to date
- [ ] GitHub secrets configured:
  - [ ] `AWS_ROLE_TO_ASSUME` (GitHub Actions IAM role ARN)
  - [ ] `TF_STATE_BUCKET` (S3 bucket for Terraform state)
  - [ ] `SLACK_WEBHOOK` (optional - for notifications)
  - [ ] `DEV_STATE_MACHINE_ARN` (after Terraform apply)
  - [ ] `PROD_STATE_MACHINE_ARN` (after Terraform apply)

### Code Review
- [ ] README.md reviewed and customized
- [ ] ARCHITECTURE.md reviewed for accuracy
- [ ] RUNBOOK.md reviewed for operations team
- [ ] All Lambda function code reviewed
- [ ] Error handling verified in all functions
- [ ] Security review completed:
  - [ ] No hardcoded credentials
  - [ ] IAM permissions are least privilege
  - [ ] Encryption is configured
  - [ ] Logging is comprehensive

---

## Terraform Deployment Phase

### Terraform Configuration
- [ ] `terraform/terraform.tfvars` created with:
  ```hcl
  environment    = "dev"
  region         = "us-east-1"
  project_name   = "migration-orchestration"
  ```
- [ ] `terraform/environments/dev.tfvars` created
- [ ] `terraform/environments/prod.tfvars` created
- [ ] Backend configuration verified in `main.tf`
- [ ] Provider version constraints set appropriately

### Terraform Modules
- [ ] `modules/sqs.tf` implemented:
  - [ ] Main queue with encryption
  - [ ] DLQ configuration
  - [ ] Visibility timeout set
  - [ ] Message retention
- [ ] `modules/eventbridge.tf` implemented:
  - [ ] Custom event bus created
  - [ ] Event rules for routing
  - [ ] Lambda targets configured
- [ ] `modules/dynamodb.tf` implemented:
  - [ ] Migration state table created
  - [ ] Global secondary indexes
  - [ ] TTL configured
  - [ ] Encryption enabled
- [ ] `modules/iam.tf` implemented:
  - [ ] Lambda execution roles
  - [ ] Step Functions service role
  - [ ] EventBridge permissions
  - [ ] Least privilege policies
- [ ] `modules/lambda.tf` implemented:
  - [ ] All 8 Lambda functions deployed
  - [ ] Environment variables set
  - [ ] VPC configuration (if needed)
  - [ ] Layers configured (if using)
- [ ] `modules/stepfunctions.tf` implemented:
  - [ ] State machine definition
  - [ ] Retry policies configured
  - [ ] Error handling with catch blocks
  - [ ] CloudWatch logging enabled
- [ ] `modules/kms.tf` implemented:
  - [ ] KMS keys created
  - [ ] Key policies configured
  - [ ] Key rotation enabled
- [ ] `modules/api-gateway.tf` implemented (optional):
  - [ ] REST API created
  - [ ] Lambda integration
  - [ ] CORS configured

### Terraform Deployment
- [ ] Terraform initialized:
  ```bash
  cd terraform
  terraform init -backend-config="bucket=<bucket>"
  ```
- [ ] Terraform validated:
  ```bash
  terraform validate
  ```
- [ ] Terraform plan created:
  ```bash
  terraform plan -out=tfplan -var-file=environments/dev.tfvars
  ```
- [ ] Plan reviewed for correctness
- [ ] Terraform applied:
  ```bash
  terraform apply tfplan
  ```
- [ ] Outputs captured:
  ```bash
  terraform output -json > outputs.json
  ```

---

## Lambda Deployment Phase

### Lambda Function Verification
- [ ] All 8 Lambda functions deployed via Terraform
- [ ] Lambda functions have correct:
  - [ ] Runtime (Python 3.11)
  - [ ] Handler paths
  - [ ] Memory allocation
  - [ ] Timeout (5+ minutes for long operations)
  - [ ] Environment variables
  - [ ] VPC configuration (if needed)
- [ ] Lambda execution roles attached:
  - [ ] DynamoDB permissions
  - [ ] EventBridge permissions
  - [ ] MGN API permissions
  - [ ] Secrets Manager permissions
  - [ ] KMS permissions
- [ ] Lambda CloudWatch logs:
  - [ ] Log groups created
  - [ ] Retention set to 30 days
  - [ ] Encryption enabled

### Lambda Testing
- [ ] Ingress handler tested:
  ```bash
  aws lambda invoke --function-name ingress-handler /dev/stdout
  ```
- [ ] All functions have valid code (no syntax errors)
- [ ] All functions can be invoked (permission checks)
- [ ] Unit tests pass:
  ```bash
  cd lambdas && pytest tests/ -v
  ```

---

## EventBridge & SQS Setup

### SQS Configuration
- [ ] Main queue created with:
  - [ ] Correct name format
  - [ ] KMS encryption enabled
  - [ ] Message retention (14 days)
  - [ ] Visibility timeout (5 minutes)
- [ ] DLQ created and linked:
  - [ ] Message retention (14 days)
  - [ ] Alarm configured
- [ ] Event source mapping created:
  - [ ] Lambda as destination
  - [ ] Batch size appropriate
  - [ ] Error handling configured

### EventBridge Configuration
- [ ] Custom event bus created
- [ ] Event rules created for:
  - [ ] MigrationRequested → Step Functions
  - [ ] MigrationStatusUpdated → Logging
  - [ ] MigrationFailed → Rollback Handler
  - [ ] MigrationSucceeded → Callback Handler
- [ ] Target Lambda functions configured with:
  - [ ] Proper IAM permissions
  - [ ] Dead letter queue (DLQ)
  - [ ] Retry policy
- [ ] Event patterns tested with sample events

---

## DynamoDB Setup

### Table Configuration
- [ ] migration-state table created with:
  - [ ] Partition key: migrationId
  - [ ] TTL: enabled (ttl attribute, 30 days)
  - [ ] Encryption: KMS enabled
  - [ ] Point-in-time recovery: enabled
- [ ] Global Secondary Indexes created:
  - [ ] statusIndex (status as PK)
  - [ ] waveIndex (wave as PK)
  - [ ] appNameIndex (appName as PK)
- [ ] Capacity configured:
  - [ ] On-demand for flexibility
  - [ ] Or provisioned with auto-scaling
- [ ] Backup enabled:
  - [ ] Daily backups
  - [ ] Cross-region replication (prod)

---

## Step Functions Setup

### State Machine Configuration
- [ ] State machine definition created:
  - [ ] Input validation step
  - [ ] Source preparation step
  - [ ] Migration trigger step
  - [ ] Status polling with retry
  - [ ] Verification step
  - [ ] Cutover finalization step
  - [ ] Error handling with catch blocks
  - [ ] Rollback path on failure
- [ ] State machine properties:
  - [ ] CloudWatch logging enabled
  - [ ] X-Ray tracing enabled
  - [ ] Execution history retention: 30 days
- [ ] State machine tested:
  - [ ] Execute with sample input
  - [ ] Verify state transitions
  - [ ] Check Lambda invocations

---

## GitHub Actions Setup

### Workflow Configuration
- [ ] GitHub Actions workflow file committed
- [ ] Workflow permissions configured:
  - [ ] OIDC token generation enabled
  - [ ] Repository read access enabled
- [ ] Secrets configured in GitHub:
  - [ ] AWS_ROLE_TO_ASSUME set
  - [ ] TF_STATE_BUCKET set
  - [ ] SLACK_WEBHOOK set (optional)
- [ ] Branch protection includes:
  - [ ] Workflow must pass

### Workflow Testing
- [ ] Push to develop branch triggers workflow
- [ ] Validation stage passes
- [ ] Plan stage generates Terraform plan
- [ ] Lambda build creates artifacts
- [ ] Dev deployment completes (if automated)
- [ ] PR to main branch triggers validation only
- [ ] Main branch deployment requires approval

---

## Testing Phase

### Unit Tests
- [ ] All unit tests pass:
  ```bash
  cd lambdas && pytest tests/ -v --cov=.
  ```
- [ ] Test coverage acceptable (>80%)
- [ ] No test warnings or errors

### Integration Tests
- [ ] Deploy to dev environment
- [ ] Send test migration message:
  ```bash
  aws sqs send-message --queue-url <URL> --message-body '{...}'
  ```
- [ ] Monitor Step Functions execution
- [ ] Verify all Lambda functions invoked
- [ ] Check DynamoDB state updates
- [ ] Verify CloudWatch logs

### Manual Testing
- [ ] Test with actual Azure VM (if available)
- [ ] Verify MGN agent installation
- [ ] Monitor replication status
- [ ] Test verification step with mock data
- [ ] Test rollback functionality
- [ ] Verify callback delivery (if URL available)

---

## Monitoring & Observability Setup

### CloudWatch Configuration
- [ ] CloudWatch log groups created for all Lambda
- [ ] Log retention set to 30 days
- [ ] Log group encryption enabled
- [ ] Metrics enabled:
  - [ ] Lambda duration
  - [ ] Lambda errors
  - [ ] DLQ message count
  - [ ] Replication lag
- [ ] Dashboard created with key metrics:
  - [ ] Migration success rate
  - [ ] Average migration time
  - [ ] Error rate by type
  - [ ] Queue depth
  - [ ] DLQ messages

### Alarms Configuration
- [ ] DLQ message alarm (threshold: > 5)
- [ ] Lambda error rate alarm (threshold: > 1%)
- [ ] Step Functions failure alarm (threshold: > 2/hour)
- [ ] Replication lag alarm (threshold: > 10 min)
- [ ] SNS topic created for notifications
- [ ] Email/Slack subscription confirmed

### X-Ray Configuration
- [ ] X-Ray sampling configured
- [ ] X-Ray tracing enabled in:
  - [ ] Lambda functions
  - [ ] Step Functions
  - [ ] EventBridge
- [ ] Service map accessible in X-Ray console

---

## Security Verification

### IAM Review
- [ ] All Lambda roles reviewed for least privilege
- [ ] Step Functions role has minimal permissions
- [ ] EventBridge rules have scoped permissions
- [ ] No overly permissive wildcards (*)
- [ ] Cross-account access not used (unless needed)
- [ ] Root account not used for operations

### Encryption Review
- [ ] SQS encrypted with KMS
- [ ] DynamoDB encrypted with KMS
- [ ] Lambda environment variables encrypted
- [ ] S3 state file encrypted
- [ ] KMS key rotation enabled
- [ ] KMS key policies reviewed

### Network Security (if applicable)
- [ ] Lambda in VPC (if required)
- [ ] Security groups configured restrictively
- [ ] VPC endpoints for AWS services
- [ ] No public Lambda endpoints (unless API Gateway)
- [ ] Network ACLs configured

### Credential Management
- [ ] No hardcoded credentials in code
- [ ] Credentials in Secrets Manager only
- [ ] Credentials rotated regularly
- [ ] IAM user keys rotated (if any)
- [ ] GitHub secrets reviewed

---

## Production Readiness

### Code Quality
- [ ] Code passes linting checks
- [ ] Code follows naming conventions
- [ ] Comments present for complex logic
- [ ] Error handling comprehensive
- [ ] Logging is structured (JSON)
- [ ] No TODO/FIXME comments left

### Documentation
- [ ] README.md complete and accurate
- [ ] ARCHITECTURE.md reviewed
- [ ] RUNBOOK.md complete
- [ ] Code comments accurate
- [ ] API documentation complete
- [ ] Deployment guide tested

### Performance & Scalability
- [ ] Lambda memory allocation optimized
- [ ] Step Functions timeout appropriate
- [ ] DynamoDB capacity provisioned
- [ ] Retry policies configured
- [ ] Exponential backoff implemented
- [ ] Concurrency limits set

### Cost Optimization
- [ ] Lambda memory sized correctly
- [ ] DynamoDB on-demand evaluated
- [ ] Data transfer costs minimized
- [ ] KMS key usage optimized
- [ ] Unused resources removed
- [ ] Cost estimate reviewed

### Backup & Disaster Recovery
- [ ] DynamoDB backups configured
- [ ] S3 state versioning enabled
- [ ] Terraform state backup plan
- [ ] Migration rollback tested
- [ ] Disaster recovery runbook created
- [ ] RTO/RPO defined

---

## Production Deployment Phase

### Pre-Deployment
- [ ] Change management ticket created
- [ ] Stakeholders notified
- [ ] Rollback plan documented
- [ ] On-call team briefed
- [ ] Maintenance window scheduled (if needed)
- [ ] Backup of current state taken

### Deployment
- [ ] Terraform plan reviewed (prod)
- [ ] Deployment approval obtained
- [ ] Main branch deployment triggered
- [ ] GitHub Actions workflow completes
- [ ] All resources deployed successfully
- [ ] Health checks pass

### Post-Deployment
- [ ] Production monitoring verified
- [ ] All alarms active and tested
- [ ] Dashboard showing correct data
- [ ] Log aggregation working
- [ ] First production migration tested (optional)
- [ ] Team notified of completion
- [ ] Documentation updated with prod URLs

---

## Ongoing Operations

### Daily Tasks
- [ ] Monitor CloudWatch dashboards
- [ ] Check for DLQ messages
- [ ] Review error logs
- [ ] Verify Step Functions executions

### Weekly Tasks
- [ ] Review metrics and trends
- [ ] Update dependencies (Python)
- [ ] Backup DynamoDB data
- [ ] Test rollback procedures

### Monthly Tasks
- [ ] Security audit
- [ ] Cost review
- [ ] Performance optimization
- [ ] Dependency updates (Terraform)

### Quarterly Tasks
- [ ] Disaster recovery drill
- [ ] Capacity planning
- [ ] Security assessment
- [ ] Architecture review

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Project Manager | | | |
| Security Team | | | |
| Operations Team | | | |
| DevOps Lead | | | |
| Development Lead | | | |

---

## Notes

- Keep this checklist for audit trail
- Update as processes change
- Reference during incidents
- Review quarterly for relevance

**Checklist Version**: 1.0  
**Last Updated**: 2024-01-XX  
**Next Review**: 2024-04-XX
