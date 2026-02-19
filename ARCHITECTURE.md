# Architecture Documentation

## System Overview

The Event-Driven Migration Orchestration Framework is a serverless, event-driven system designed to automate the migration of 100+ VMs from Azure to AWS using AWS MGN, Cloud Migration Factory, and AWS serverless services.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Migration Request Sources                    │
│         GitHub Actions | API Gateway | External Systems         │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │   SQS Queue  │
                        └──────┬───────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │ Ingress Lambda  │
                        └──────┬──────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    EventBridge       │
                    │  Custom Event Bus    │
                    └──────┬───────────────┘
                           │
                    ┌──────┴──────────┐
                    │                 │
                    ▼                 ▼
            ┌────────────────┐  ┌──────────────┐
            │ Step Functions │  │ CloudWatch   │
            │ State Machine  │  │ (Monitoring) │
            └────┬─────┬─────┘  └──────────────┘
                 │     │
        ┌────────┴─┬───┴────────┐
        │          │            │
        ▼          ▼            ▼
    ┌────────────────────────────────────────┐
    │     Stateless Lambda Functions         │
    │ ────────────────────────────────────── │
    │ • Validate Input                       │
    │ • Prepare Source (Azure/VMware)       │
    │ • Trigger Migration (MGN)              │
    │ • Verify Migration Status              │
    │ • Finalize Cutover                    │
    │ • Rollback on Failure                 │
    │ • Send Callbacks                      │
    └─────┬──────────────────────────────────┘
          │
    ┌─────┴────────────────────┬──────────┐
    │                          │          │
    ▼                          ▼          ▼
┌─────────┐            ┌──────────────┐ ┌──────────┐
│ AWS MGN │            │  DynamoDB    │ │   KMS    │
│         │            │ (State Table)│ │(Encrypt.)│
└─────────┘            └──────────────┘ └──────────┘
    │
    ▼
┌────────────────────┐
│ Target AWS Account │
│ ────────────────── │
│ • EC2 Instances    │
│ • VPC Networks     │
│ • Security Groups  │
└────────────────────┘
```

## Component Details

### 1. Message Ingestion Layer

#### SQS Queue
- **Purpose**: Decouples migration requests from processing
- **Configuration**:
  - Visibility timeout: 900 seconds (15 minutes)
  - Message retention: 14 days
  - KMS encryption: Enabled
  - Dead Letter Queue: Enabled (3 retries)

#### API Gateway
- **Endpoints**:
  - `POST /migrations` - Submit new migration
  - `POST /migrations/test` - Submit test launch
- **Features**:
  - CORS enabled for cross-origin requests
  - Request validation
  - Throttling: 50 req/sec (configurable)
  - CloudWatch logging

#### Ingress Handler Lambda
- **Function**: Receives SQS messages, validates schema, publishes to EventBridge
- **Responsibilities**:
  - JSON schema validation
  - Correlation ID generation
  - Event enrichment
  - Error handling
- **Timeout**: 300 seconds
- **Memory**: 512 MB
- **Triggers**: SQS event source (batch size: 10)

### 2. Event Routing Layer

#### EventBridge Custom Bus
- **Purpose**: Routes events to appropriate consumers
- **Event Pattern Matching**:
  - Source: `migration.ingress`, `migration.orchestration`
  - Detail Type: `Migration Request Received`, `Migration Completed`

#### EventBridge Rules
1. **Ingress Rule** → Step Functions State Machine
2. **Success Rule** → CloudWatch/Metrics
3. **Failure Rule** → SNS Notifications

### 3. Orchestration Layer

#### Step Functions State Machine
- **Name**: Migration Orchestration State Machine
- **Type**: Standard State Machine (15-minute execution max configurable)
- **States**:
  1. **ValidateInput**: Verify prerequisites
  2. **PrepareSource**: Configure source VM
  3. **TriggerMigration**: Initiate MGN launch
  4. **WaitBeforeVerification**: 30-second delay
  5. **VerifyMigration**: Check status
  6. **CheckVerificationStatus**: Decision point
  7. **WaitAndRetryVerification**: Exponential backoff
  8. **FinalizeCutover**: Complete migration
  9. **MigrationSucceeded**: Send success callback
  10. **Rollback**: Handle failures
  11. **MigrationFailed**: Send failure notification

#### State Machine Features
- Automatic retry with exponential backoff
- Error handling with Catch blocks
- Parallel branch execution (future enhancement)
- CloudWatch logging: Full execution history
- X-Ray tracing: End-to-end observability

### 4. Processing Layer

#### Lambda Functions

**Validate Input** (`validate_input.py`)
- Validates migration payload against JSON schema
- Checks MGN/CMF prerequisites
- Verifies source/target connectivity
- Timeout: 300s | Memory: 512MB

**Prepare Source** (`prepare_source.py`)
- Installs MGN replication agent
- Creates VM snapshots
- Records pre-migration state
- Validates source readiness
- Timeout: 900s | Memory: 1024MB

**Trigger Migration** (`trigger_migration.py`)
- Calls AWS MGN APIs to initiate migration
- Manages CMF wave transitions
- Handles both test and cutover launches
- Timeout: 300s | Memory: 512MB

**Verify Migration** (`verify_migration_new.py`)
- Polls MGN job status
- Checks replication lag
- Verifies application health
- Publishes CloudWatch metrics
- Timeout: 600s | Memory: 512MB

**Finalize Cutover** (`finalize_cutover.py`)
- Performs final cutover steps
- Updates DNS/IP configurations
- Updates CMDB/runbooks
- Validates target application
- Timeout: 600s | Memory: 512MB

**Rollback Handler** (`rollback_handler_new.py`)
- Terminates target instances
- Restores source VM from snapshots
- Cancels MGN jobs
- Sends notifications
- Timeout: 600s | Memory: 512MB

**Callback Handler** (`callback_handler_new.py`)
- Sends status to external systems
- Updates CMDB
- Handles custom webhooks
- Timeout: 300s | Memory: 512MB

### 5. State Management Layer

#### DynamoDB Table
- **Table Name**: `{project_name}-migration-state`
- **Partition Key**: `migrationId` (String)
- **Attributes**:
  ```
  {
    "migrationId": "mig-12345",
    "status": "COMPLETED",
    "wave": "wave-3",
    "appName": "billing-app",
    "createdAt": 1234567890,
    "updatedAt": 1234567890,
    "sourceState": { /* pre-migration snapshot */ },
    "jobId": "job-123",
    "jobStatus": "COMPLETED",
    "replicationLag": 0,
    "healthStatus": "healthy"
  }
  ```

#### Global Secondary Indexes
1. **wave-status-index**
   - Partition Key: `wave`
   - Sort Key: `status`
   - Use Case: Query migrations by wave

2. **app-status-index**
   - Partition Key: `appName`
   - Sort Key: `status`
   - Use Case: Query by application

3. **status-timestamp-index**
   - Partition Key: `status`
   - Sort Key: `updatedAt`
   - Use Case: Query by status with timestamp

#### TTL Policy
- Attribute: `expiresAt`
- Auto-deletes completed migrations after 90 days
- Saves storage costs

### 6. Security Layer

#### KMS Encryption Keys
- **Lambda Key**: Encrypts environment variables
- **SQS Key**: Encrypts message content
- **DynamoDB Key**: Encrypts table data
- **SNS Key**: Encrypts notifications
- **Logs Key**: Encrypts CloudWatch logs

#### IAM Roles & Policies
- **Lambda Execution Role**:
  - SQS access (send, receive, delete)
  - DynamoDB access (read, write, query)
  - EventBridge (put events)
  - MGN APIs (read-only)
  - EC2 APIs (read, terminate)
  - SNS (publish)
  - CloudWatch (metrics, logs)
  - KMS (decrypt, generate)

- **Step Functions Role**:
  - Lambda invocation
  - EventBridge (put events)
  - CloudWatch Logs (write)

- **EventBridge Role**:
  - Step Functions (start execution)
  - SQS (send to DLQ)

- **API Gateway Role**:
  - SQS (send message)

### 7. Observability Layer

#### CloudWatch Logs
- **Log Groups**:
  - `/aws/lambda/migration-orchestration-*` (per Lambda)
  - `/aws/states/migration-orchestration` (Step Functions)
  - `/aws/apigateway/migration-orchestration` (API Gateway)

- **Log Format**: Structured JSON with:
  ```json
  {
    "timestamp": 1234567890,
    "level": "INFO",
    "logger": "module_name",
    "correlationId": "mig-abc123def456",
    "message": "Action completed",
    "migrationId": "mig-12345",
    "details": { /* context */ }
  }
  ```

#### CloudWatch Metrics
- **Namespace**: `MigrationOrchestration`
- **Metrics**:
  - `ReplicationLag`: Seconds (Lower is better)
  - `HealthStatus`: 0/1 (1 = healthy)
  - `MigrationDuration`: Seconds
  - `SuccessRate`: Percentage

#### CloudWatch Dashboard
- Real-time monitoring of key metrics
- Auto-generated from Terraform
- 5-minute refresh rate

#### X-Ray Tracing
- Traces Lambda→Lambda calls
- Traces Lambda→AWS service calls
- Service map visualization
- Performance bottleneck identification

#### Alarms
- **SQS DLQ**: Alert when messages appear
- **DynamoDB Throttle**: Alert on throttling events
- **Lambda Errors**: Alert on function failures
- **API Errors**: Alert on 5xx responses

### 8. CI/CD Pipeline

#### GitHub Actions Workflow
1. **Plan Stage**:
   - Checkout code
   - Initialize Terraform
   - Validate configuration
   - Generate plan
   - Upload artifact

2. **Build Stage**:
   - Build Lambda functions
   - Run unit tests
   - Generate coverage report
   - Package artifacts

3. **Deploy Stage**:
   - Download artifacts
   - Apply Terraform
   - Export outputs
   - Notify on completion

4. **Test Stage**:
   - Run integration tests
   - Validate API endpoints
   - Check MGN integration

5. **Rollback Stage** (on failure):
   - Automatic rollback to previous version
   - Notifications sent to team

## Data Flow

### Happy Path: Migration Request

```
1. User submits request via API or GitHub
   ↓
2. API Gateway → SQS Queue
   ↓
3. Ingress Handler Lambda processes SQS message
   ├─ Validates JSON schema
   ├─ Generates correlation ID
   ├─ Enriches event
   └─ Publishes to EventBridge
   ↓
4. EventBridge routes to Step Functions
   ↓
5. Step Functions executes state machine
   ├─ ValidateInput Lambda
   │  └─ Checks MGN/CMF prerequisites
   │
   ├─ PrepareSource Lambda
   │  ├─ Installs agents
   │  └─ Creates snapshots
   │
   ├─ TriggerMigration Lambda
   │  └─ Calls MGN APIs
   │
   ├─ VerifyMigration Lambda (with polling)
   │  ├─ Checks job status
   │  ├─ Verifies health
   │  └─ Publishes metrics
   │
   └─ FinalizeCutover Lambda
      ├─ Updates DNS
      └─ Updates CMDB
   ↓
6. Callback Handler sends status to external system
   ↓
7. Success event published to EventBridge
   ↓
8. SNS notification sent to team
```

### Error Path: Migration Failure

```
1. Validation/Verification fails
   ↓
2. Step Functions catches error
   ↓
3. Rollback Handler invoked
   ├─ Terminates target instance
   ├─ Restores source VM
   └─ Cancels MGN jobs
   ↓
4. Callback Handler sends failure status
   ↓
5. Failure event published to EventBridge
   ↓
6. SNS critical alert sent to team
   ↓
7. Manual investigation required
```

## Performance Characteristics

### Latency
- Ingress → EventBridge: < 100ms
- Validation: 5-10 seconds
- Preparation: 5-15 minutes (depends on source)
- Migration: 30 minutes - 2 hours (depends on data size)
- Verification: 2-5 minutes (with polling)
- Total end-to-end: 45 minutes - 3 hours

### Throughput
- **SQS**: 300 messages/second per partition
- **Lambda**: Concurrent executions: 1000 (configurable)
- **DynamoDB**: On-demand (auto-scaling)
- **EventBridge**: 10,000 events/second

### Scalability
- SQS automatically scales
- Lambda scales with SQS batch size
- DynamoDB on-demand pricing
- Step Functions: 25,000 state machines concurrently

## Security Considerations

### Network Security
- All data encrypted in transit (TLS 1.2+)
- KMS encryption for data at rest
- SQS dead-letter queue for failed messages
- VPC optional for Lambda (can isolate in private subnets)

### Identity & Access
- IAM roles follow least-privilege principle
- GitHub OIDC for CI/CD authentication
- No hardcoded credentials
- Secrets Manager for sensitive data

### Audit & Compliance
- CloudTrail logging all API calls
- CloudWatch detailed logging
- X-Ray tracing for compliance
- DynamoDB point-in-time recovery

## Cost Optimization

### Budget Estimation (Monthly)
- SQS: $0.50-5 (based on message volume)
- Lambda: $10-50 (based on execution time)
- DynamoDB: $1-10 (on-demand pricing)
- EventBridge: $1-5 (based on events)
- KMS: $1/key (5 keys = $5)
- CloudWatch: $5-15 (logs + metrics)
- **Total**: ~$20-80/month for 100 migrations

### Cost Reduction Strategies
- Use DynamoDB on-demand (variable workload)
- Set appropriate Lambda timeouts
- Delete old logs (adjust retention)
- Consolidate KMS keys if possible

## Disaster Recovery

### RTO (Recovery Time Objective): 1 hour
### RPO (Recovery Point Objective): 15 minutes

### Backup Strategy
- DynamoDB point-in-time recovery (enabled)
- Terraform state in S3 with versioning
- Lambda code in GitHub (version control)

### Failover Procedure
1. Restore DynamoDB from backup
2. Redeploy Lambda functions
3. Check EventBridge rules
4. Verify SQS queue integrity
5. Resume migrations

## Future Enhancements

1. **Parallel Processing**: Process multiple migrations concurrently
2. **Custom Metrics**: Application-specific health checks
3. **Advanced Rollback**: Partial rollback to specific point-in-time
4. **ML-based Prediction**: Estimate migration duration
5. **Multi-region Support**: Replicate infrastructure across regions
6. **GraphQL API**: Advanced querying of migration status
7. **Mobile App**: Mobile dashboard for monitoring
8. **Custom Webhooks**: More flexible integration options

## References

- [AWS MGN Documentation](https://docs.aws.amazon.com/mgn/)
- [AWS Step Functions Documentation](https://docs.aws.amazon.com/stepfunctions/)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest)
