# Architecture Documentation

## System Overview

The migration orchestration framework is built on event-driven serverless architecture using AWS services to provide a scalable, reliable, and automated migration process for large-scale VM migrations.

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitHub Actions                          │
│                      (Deployment Pipeline)                      │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                    API Gateway (Optional)                        │
│                  HTTP → SQS Bridge                               │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  SQS Queue (Migration Requests)                                  │
│  ├── Main Queue                                                  │
│  ├── Dead Letter Queue (DLQ)                                     │
│  ├── Encryption: KMS                                             │
│  └── Visibility Timeout: 5 min                                   │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  Ingress Lambda                                                  │
│  ├── Parses SQS messages                                         │
│  ├── Validates schema                                            │
│  ├── Generates correlation IDs                                   │
│  └── Publishes MigrationRequested event                          │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│              EventBridge Custom Bus                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Events:                                                     │ │
│  │ - MigrationRequested                                        │ │
│  │ - MigrationValidated                                        │ │
│  │ - MigrationStatusUpdated                                    │ │
│  │ - MigrationSucceeded                                        │ │
│  │ - MigrationFailed                                           │ │
│  │ - MigrationRolledBack                                       │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│             Step Functions State Machine                         │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │  Validate    │  →   │   Prepare    │  →   │   Trigger    │  │
│  │    Input     │      │    Source    │      │  Migration   │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│       ↓                                              ↓           │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   Verify     │  ←   │  Poll Status │  ←   │   Execute    │  │
│  │ Migration    │      │  (Retry)     │      │  Migration   │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│       ↓                                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │        Success Path → Finalize Cutover                   │  │
│  │        Failure Path → Rollback Handler                   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         ↓                                              ↓
    Success Event                                 Failure Event
         ↓                                              ↓
┌──────────────────────┐                    ┌──────────────────────┐
│  Callback Lambda     │                    │  Callback Lambda     │
│  (Success Handler)   │                    │  (Error Handler)     │
└──────────────────────┘                    └──────────────────────┘
         ↓                                              ↓
    External Systems                         Notification System
```

## Data Flow

### 1. Migration Request Ingestion

```
User/GitHub Action
    ↓ (POST)
API Gateway / SQS
    ↓ (Add to queue)
SQS Queue
    ↓ (Event source mapping)
Ingress Lambda
    ↓ (Validate schema)
    ├─ Valid: Publish MigrationRequested event
    └─ Invalid: Send to DLQ
```

### 2. Migration Workflow Execution

```
MigrationRequested Event
    ↓ (EventBridge Rule)
Step Functions State Machine
    ├─ Validate Input Lambda
    │   ├─ Check AWS prerequisites
    │   ├─ Verify MGN availability
    │   └─ Update DynamoDB state
    │
    ├─ Prepare Source Lambda
    │   ├─ Install MGN agent
    │   ├─ Create snapshots
    │   └─ Validate readiness
    │
    ├─ Trigger Migration Lambda
    │   ├─ Call MGN API
    │   ├─ Update CMF wave
    │   └─ Store job ID
    │
    ├─ Poll Status Lambda (with retry/backoff)
    │   ├─ Check replication lag
    │   ├─ Validate health
    │   └─ Exponential backoff retry
    │
    ├─ Success Path:
    │   ├─ Finalize Cutover Lambda
    │   │   ├─ Update DNS
    │   │   ├─ Decommission source
    │   │   ├─ Update CMDB
    │   │   └─ Publish success event
    │   └─ Callback Lambda
    │       └─ Send status to external systems
    │
    └─ Failure Path:
        ├─ Rollback Handler Lambda
        │   ├─ Stop replication
        │   ├─ Terminate target
        │   ├─ Restore source
        │   └─ Publish rollback event
        └─ Callback Lambda
            └─ Send error notification
```

## State Management

### DynamoDB Table Structure

```
migrationId (PK)
├── status (GSI: statusIndex)
├── wave (GSI: waveIndex)
├── appName (GSI: appNameIndex)
├── source
├── target
├── environment
├── updatedAt
├── correlationId
├── executionDetails
│   ├── validation
│   ├── sourcePreparation
│   ├── mgn
│   ├── replication
│   ├── cutover
│   └── error (if failed)
└── ttl (30 days)
```

### State Transitions

```
PENDING
  ↓ (Ingress validates)
VALIDATED
  ↓ (Source prep completes)
SOURCE_PREPARED
  ↓ (Migration triggered)
MIGRATION_IN_PROGRESS
  ↓ (Verification succeeds)
VERIFIED
  ↓ (Cutover completes)
COMPLETED
  ↓ (Success event)
SUCCESS

OR

[Any State] + Error
  ↓ (Catch block triggered)
ROLLED_BACK
  ↓ (Rollback completes)
FAILED
```

## Security Architecture

### Authentication & Authorization

```
┌────────────────────────────────────────┐
│      GitHub Actions OIDC Provider      │
│  ├── Authenticated by GitHub token     │
│  └── Assumes AWS role via STS          │
└────────────────────────────────────────┘
           ↓
┌────────────────────────────────────────┐
│      AWS IAM Role (GitHub Actions)     │
│  ├── Assume role policy via OIDC       │
│  ├── Minimal permissions               │
│  ├── Limited to Terraform actions      │
│  └── Scoped to specific resources      │
└────────────────────────────────────────┘
           ↓
┌────────────────────────────────────────┐
│    Lambda Execution Roles              │
│  ├── Per-function execution role       │
│  ├── Least privilege policies          │
│  ├── Resource-specific permissions     │
│  └── Service-specific API access       │
└────────────────────────────────────────┘
```

### Encryption Architecture

```
┌─────────────────────────────────────┐
│        KMS Master Keys              │
│  ├── SQS Encryption Key             │
│  ├── DynamoDB Encryption Key        │
│  ├── Lambda Env Var Key             │
│  └── S3 State File Key              │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│    Data at Rest Encryption          │
│  ├── SQS messages encrypted         │
│  ├── DynamoDB items encrypted       │
│  ├── Lambda env vars encrypted      │
│  └── S3 state encrypted             │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│    Data in Transit Encryption       │
│  ├── TLS 1.2+ for all APIs          │
│  ├── EventBridge → Lambda (HTTPS)   │
│  ├── AWS SDK encrypted connections  │
│  └── Secrets Manager encrypted      │
└─────────────────────────────────────┘
```

### Network Isolation

```
┌──────────────────────────────────────┐
│         VPC (Optional)               │
│  ┌────────────────────────────────┐  │
│  │   Private Subnets              │  │
│  │  ├── Lambda Functions          │  │
│  │  ├── VPC Endpoints             │  │
│  │  │   ├── S3 Gateway            │  │
│  │  │   ├── DynamoDB Gateway      │  │
│  │  │   ├── EventBridge Interface │  │
│  │  │   └── SQS Interface         │  │
│  │  └── Security Groups           │  │
│  │      └── Restricted ports      │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │   NAT Gateway                  │  │
│  │   (For AWS API calls)          │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

## Observability Architecture

### Logging Flow

```
Lambda Functions
    ↓
CloudWatch Logs
├── /aws/lambda/ingress-handler
├── /aws/lambda/validate-input
├── /aws/lambda/prepare-source
├── /aws/lambda/trigger-migration
├── /aws/lambda/verify-migration
├── /aws/lambda/finalize-cutover
├── /aws/lambda/callback-handler
└── /aws/lambda/rollback-handler
    ↓
Log Insights Queries
├── Error tracking
├── Performance analysis
├── Correlation ID tracking
└── Cost analysis
```

### Metrics Collection

```
Lambda Functions
    ↓ (Custom metrics)
CloudWatch Metrics
├── Migration success rate
├── Migration duration
├── Replication lag
├── Error rate by type
├── DLQ message count
└── Step Functions duration
    ↓
CloudWatch Dashboards
└── Real-time monitoring
```

### Distributed Tracing

```
GitHub Action
    ↓ (Generates correlation ID)
SQS Message
    ↓ (Contains correlation ID)
Ingress Lambda
    ↓ (Injects into event)
EventBridge Event
    ↓ (Passes correlation ID)
Step Functions
    ↓ (Tracks in execution)
Lambda Functions
    ↓ (Log with correlation ID)
CloudWatch Logs
    ↓ (Filter by correlation ID)
Request Timeline
```

## Disaster Recovery

### Failure Scenarios

1. **Lambda Timeout**: Step Functions retries or triggers rollback
2. **API Failure**: Exponential backoff retry in state machine
3. **DynamoDB Throttling**: Step Functions handles with backoff
4. **EventBridge Delivery Failure**: DLQ captures for replay
5. **Complete Service Failure**: Rollback handler restores state

### Recovery Procedures

```
Detection
    ↓
Alert (CloudWatch Alarm)
    ↓
On-Call Response
    ├─ Automatic: Rollback triggered
    ├─ Manual: Review execution history
    └─ Manual: Approve rollback if needed
    ↓
Rollback Lambda
├── Stops MGN replication
├── Terminates target
├── Restores source
└── Notifies stakeholders
    ↓
Post-Incident
├── Review logs
├── Update state in DynamoDB
├── Notify customer
└── Document lessons learned
```

## Performance Characteristics

### Throughput

- **Concurrent Migrations**: 100+ parallel executions
- **Migration Rate**: ~10 migrations/minute (configurable)
- **State Machine Execution Time**: 30-120 minutes per migration

### Latency

- **Event Processing**: < 1 second (SQS to Lambda)
- **State Transitions**: < 5 seconds
- **API Calls**: < 30 seconds (with retries)

### Cost Optimization

- **Lambda Pricing**: Per 100ms execution
- **DynamoDB**: On-demand or provisioned capacity
- **EventBridge**: Per million events
- **Data Transfer**: Minimize cross-region calls

## Scaling Considerations

### Horizontal Scaling

- EventBridge automatically scales to millions of events/sec
- Step Functions executes 100,000+ concurrent executions
- Lambda automatically scales concurrent executions
- DynamoDB on-demand handles unlimited throughput

### Vertical Scaling

- Lambda memory: 128MB to 10GB
- Step Functions: Depends on execution history size
- DynamoDB: Item size < 400KB

### Bottleneck Mitigation

1. **SQS Visibility Timeout**: Set to max Lambda timeout
2. **Step Functions Retry**: Exponential backoff with jitter
3. **DynamoDB TTL**: Auto-delete old records
4. **CloudWatch Logs Retention**: 30 days default

## Integration Points

### Inbound Integrations

1. **GitHub Actions**: OIDC authentication
2. **SQS**: Migration request queue
3. **API Gateway**: REST API for manual triggers
4. **CMF**: Wave management integration

### Outbound Integrations

1. **AWS MGN**: Migration service API
2. **Route53**: DNS updates
3. **Secrets Manager**: Credential storage
4. **SNS/Email**: Notifications
5. **External Callbacks**: Custom webhooks
6. **CMDB**: Configuration management

## Deployment Architecture

### Infrastructure as Code

```
Terraform
├── Root Module
├── Network Module (VPC, Subnets)
├── Security Module (IAM, KMS)
├── Data Module (DynamoDB, S3)
├── Compute Module (Lambda, Step Functions)
├── Integration Module (EventBridge, SQS)
└── Monitoring Module (CloudWatch, X-Ray)
```

### CI/CD Pipeline

```
Code Push
    ↓
GitHub Actions
├── Validate Terraform
├── Build Lambda artifacts
├── Run unit tests
├── Generate plan
└── Require approval (prod)
    ↓
Terraform Apply
├── Create/update resources
├── Deploy Lambda functions
└── Update state file
    ↓
Post-Deployment
├── Run integration tests
├── Verify connectivity
└── Monitor for errors
```

## Future Enhancements

1. **Multi-Region Deployment**: Active-passive failover
2. **Advanced Analytics**: ML-based anomaly detection
3. **Cost Optimization**: Reserved capacity recommendations
4. **Custom Rules Engine**: Flexible migration policies
5. **Mobile Notifications**: Real-time status updates
6. **Webhook Management**: Customer-defined webhooks
7. **Audit Logging**: Compliance tracking
8. **Policy Enforcement**: Automated compliance checks
