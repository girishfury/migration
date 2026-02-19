terraform {
  required_version = ">= 1.14.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.33.0"
    }
  }

  backend "s3" {
    bucket         = "your-terraform-state-bucket"
    key            = "event-driven-migration/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project_name
      ManagedBy   = "Terraform"
      CreatedAt   = timestamp()
    }
  }
}

# KMS Module for encryption
module "kms" {
  source = "./modules/kms"

  environment  = var.environment
  project_name = var.project_name
  region       = var.region
}

# SQS Module for message queue
module "sqs" {
  source = "./modules/sqs"

  environment  = var.environment
  project_name = var.project_name
  kms_key_id   = module.kms.sqs_key_id
}

# DynamoDB Module for state management
module "dynamodb" {
  source = "./modules/dynamodb"

  environment  = var.environment
  project_name = var.project_name
  kms_key_id   = module.kms.dynamodb_key_id
}

# IAM Module for roles and policies
module "iam" {
  source = "./modules/iam"

  environment      = var.environment
  project_name     = var.project_name
  sqs_queue_arn    = module.sqs.queue_arn
  dynamodb_table   = module.dynamodb.table_name
  kms_key_arns     = [module.kms.lambda_key_arn, module.kms.sqs_key_arn, module.kms.dynamodb_key_arn]
}

# EventBridge Module for event routing
module "eventbridge" {
  source = "./modules/eventbridge"

  environment      = var.environment
  project_name     = var.project_name
  stepfunctions_arn = module.stepfunctions.state_machine_arn
}

# Lambda Module for Lambda functions
module "lambda" {
  source = "./modules/lambda"

  environment             = var.environment
  project_name            = var.project_name
  sqs_queue_url           = module.sqs.queue_url
  sqs_dlq_url             = module.sqs.dlq_url
  dynamodb_table_name     = module.dynamodb.table_name
  lambda_execution_role   = module.iam.lambda_execution_role_arn
  kms_key_id              = module.kms.lambda_key_id
  sns_topic_arn           = aws_sns_topic.migration_notifications.arn

  depends_on = [
    module.iam,
    module.sqs,
    module.dynamodb
  ]
}

# Step Functions Module for orchestration
module "stepfunctions" {
  source = "./modules/stepfunctions"

  environment              = var.environment
  project_name             = var.project_name
  stepfunctions_role_arn   = module.iam.stepfunctions_execution_role_arn
  validate_input_arn       = module.lambda.validate_input_lambda_arn
  prepare_source_arn       = module.lambda.prepare_source_lambda_arn
  trigger_migration_arn    = module.lambda.trigger_migration_lambda_arn
  verify_migration_arn     = module.lambda.verify_migration_lambda_arn
  finalize_cutover_arn     = module.lambda.finalize_cutover_lambda_arn
  rollback_handler_arn     = module.lambda.rollback_handler_lambda_arn
  callback_handler_arn     = module.lambda.callback_handler_lambda_arn

  depends_on = [module.lambda]
}

# API Gateway Module for HTTP endpoint
module "api_gateway" {
  source = "./modules/api-gateway"

  environment              = var.environment
  project_name             = var.project_name
  sqs_queue_url            = module.sqs.queue_url
  ingress_handler_arn      = module.lambda.ingress_handler_lambda_arn
  ingress_handler_role_arn = module.iam.api_gateway_execution_role_arn

  depends_on = [module.lambda]
}

# SNS Topic for notifications
resource "aws_sns_topic" "migration_notifications" {
  name              = "${var.project_name}-migration-notifications"
  kms_master_key_id = module.kms.sns_key_id

  tags = {
    Name = "${var.project_name}-notifications"
  }
}

resource "aws_sns_topic_policy" "migration_notifications" {
  arn = aws_sns_topic.migration_notifications.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.migration_notifications.arn
      }
    ]
  })
}

# CloudWatch Log Group for migration orchestration
resource "aws_cloudwatch_log_group" "migration_logs" {
  name              = "/aws/migration/${var.project_name}"
  retention_in_days = 30
  kms_key_id        = module.kms.logs_key_arn

  tags = {
    Name = "${var.project_name}-logs"
  }
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "migration_dashboard" {
  dashboard_name = "${var.project_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["MigrationOrchestration", "ReplicationLag"],
            [".", "HealthStatus"],
            ["AWS/Lambda", "Duration"],
            ["AWS/Lambda", "Errors"],
            ["AWS/States", "ExecutionsFailed"],
            ["AWS/States", "ExecutionsSucceeded"]
          ]
          period = 300
          stat   = "Average"
          region = var.region
          title  = "Migration Metrics"
        }
      }
    ]
  })
}
