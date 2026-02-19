variable "environment" {
  type = string
}

variable "project_name" {
  type = string
}

variable "sqs_queue_url" {
  type = string
}

variable "sqs_dlq_url" {
  type = string
}

variable "dynamodb_table_name" {
  type = string
}

variable "lambda_execution_role" {
  type = string
}

variable "kms_key_id" {
  type = string
}

variable "sns_topic_arn" {
  type = string
}

# Data source for current AWS region
data "aws_region" "current" {}

# Ingress Handler Lambda
resource "aws_lambda_function" "ingress_handler" {
  filename      = data.archive_file.ingress_handler.output_path
  function_name = "${var.project_name}-ingress-handler"
  role          = var.lambda_execution_role
  handler       = "ingress_handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
      KMS_KEY_ID     = var.kms_key_id
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [data.archive_file.ingress_handler]
}

# Validate Input Lambda
resource "aws_lambda_function" "validate_input" {
  filename      = data.archive_file.validate_input.output_path
  function_name = "${var.project_name}-validate-input"
  role          = var.lambda_execution_role
  handler       = "validate_input.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
      KMS_KEY_ID     = var.kms_key_id
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [data.archive_file.validate_input]
}

# Prepare Source Lambda
resource "aws_lambda_function" "prepare_source" {
  filename      = data.archive_file.prepare_source.output_path
  function_name = "${var.project_name}-prepare-source"
  role          = var.lambda_execution_role
  handler       = "prepare_source.lambda_handler"
  runtime       = "python3.11"
  timeout       = 900
  memory_size   = 1024

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
      KMS_KEY_ID     = var.kms_key_id
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [data.archive_file.prepare_source]
}

# Trigger Migration Lambda
resource "aws_lambda_function" "trigger_migration" {
  filename      = data.archive_file.trigger_migration.output_path
  function_name = "${var.project_name}-trigger-migration"
  role          = var.lambda_execution_role
  handler       = "trigger_migration.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
      KMS_KEY_ID     = var.kms_key_id
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [data.archive_file.trigger_migration]
}

# Verify Migration Lambda
resource "aws_lambda_function" "verify_migration" {
  filename      = data.archive_file.verify_migration.output_path
  function_name = "${var.project_name}-verify-migration"
  role          = var.lambda_execution_role
  handler       = "verify_migration_new.lambda_handler"
  runtime       = "python3.11"
  timeout       = 600
  memory_size   = 512

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
      KMS_KEY_ID     = var.kms_key_id
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [data.archive_file.verify_migration]
}

# Finalize Cutover Lambda
resource "aws_lambda_function" "finalize_cutover" {
  filename      = data.archive_file.finalize_cutover.output_path
  function_name = "${var.project_name}-finalize-cutover"
  role          = var.lambda_execution_role
  handler       = "finalize_cutover.lambda_handler"
  runtime       = "python3.11"
  timeout       = 600
  memory_size   = 512

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
      KMS_KEY_ID     = var.kms_key_id
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [data.archive_file.finalize_cutover]
}

# Rollback Handler Lambda
resource "aws_lambda_function" "rollback_handler" {
  filename      = data.archive_file.rollback_handler.output_path
  function_name = "${var.project_name}-rollback-handler"
  role          = var.lambda_execution_role
  handler       = "rollback_handler_new.lambda_handler"
  runtime       = "python3.11"
  timeout       = 600
  memory_size   = 512

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
      KMS_KEY_ID     = var.kms_key_id
      SNS_TOPIC_ARN  = var.sns_topic_arn
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [data.archive_file.rollback_handler]
}

# Callback Handler Lambda
resource "aws_lambda_function" "callback_handler" {
  filename      = data.archive_file.callback_handler.output_path
  function_name = "${var.project_name}-callback-handler"
  role          = var.lambda_execution_role
  handler       = "callback_handler_new.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
      KMS_KEY_ID     = var.kms_key_id
      LOG_LEVEL      = "INFO"
    }
  }

  depends_on = [data.archive_file.callback_handler]
}

# Archive Lambda functions
data "archive_file" "ingress_handler" {
  type        = "zip"
  source_dir  = "${path.module}/../../lambdas"
  output_path = "${path.module}/.terraform/ingress_handler.zip"
  excludes    = ["tests", "__pycache__", ".pytest_cache", "*.pyc"]
}

data "archive_file" "validate_input" {
  type        = "zip"
  source_dir  = "${path.module}/../../lambdas"
  output_path = "${path.module}/.terraform/validate_input.zip"
  excludes    = ["tests", "__pycache__", ".pytest_cache", "*.pyc"]
}

data "archive_file" "prepare_source" {
  type        = "zip"
  source_dir  = "${path.module}/../../lambdas"
  output_path = "${path.module}/.terraform/prepare_source.zip"
  excludes    = ["tests", "__pycache__", ".pytest_cache", "*.pyc"]
}

data "archive_file" "trigger_migration" {
  type        = "zip"
  source_dir  = "${path.module}/../../lambdas"
  output_path = "${path.module}/.terraform/trigger_migration.zip"
  excludes    = ["tests", "__pycache__", ".pytest_cache", "*.pyc"]
}

data "archive_file" "verify_migration" {
  type        = "zip"
  source_dir  = "${path.module}/../../lambdas"
  output_path = "${path.module}/.terraform/verify_migration.zip"
  excludes    = ["tests", "__pycache__", ".pytest_cache", "*.pyc"]
}

data "archive_file" "finalize_cutover" {
  type        = "zip"
  source_dir  = "${path.module}/../../lambdas"
  output_path = "${path.module}/.terraform/finalize_cutover.zip"
  excludes    = ["tests", "__pycache__", ".pytest_cache", "*.pyc"]
}

data "archive_file" "rollback_handler" {
  type        = "zip"
  source_dir  = "${path.module}/../../lambdas"
  output_path = "${path.module}/.terraform/rollback_handler.zip"
  excludes    = ["tests", "__pycache__", ".pytest_cache", "*.pyc"]
}

data "archive_file" "callback_handler" {
  type        = "zip"
  source_dir  = "${path.module}/../../lambdas"
  output_path = "${path.module}/.terraform/callback_handler.zip"
  excludes    = ["tests", "__pycache__", ".pytest_cache", "*.pyc"]
}

# SQS Event Source Mapping for Ingress Handler
resource "aws_lambda_event_source_mapping" "ingress_sqs" {
  event_source_arn = "arn:aws:sqs:${data.aws_region.current.name}:$(aws sts get-caller-identity --query Account --output text):${split("/", var.sqs_queue_url)[4]}"
  function_name    = aws_lambda_function.ingress_handler.function_name
  batch_size       = 10

  depends_on = [aws_lambda_function.ingress_handler]
}

# CloudWatch Log Groups for Lambda Functions
resource "aws_cloudwatch_log_group" "ingress_handler_logs" {
  name              = "/aws/lambda/${aws_lambda_function.ingress_handler.function_name}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "validate_input_logs" {
  name              = "/aws/lambda/${aws_lambda_function.validate_input.function_name}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "prepare_source_logs" {
  name              = "/aws/lambda/${aws_lambda_function.prepare_source.function_name}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "trigger_migration_logs" {
  name              = "/aws/lambda/${aws_lambda_function.trigger_migration.function_name}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "verify_migration_logs" {
  name              = "/aws/lambda/${aws_lambda_function.verify_migration.function_name}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "finalize_cutover_logs" {
  name              = "/aws/lambda/${aws_lambda_function.finalize_cutover.function_name}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "rollback_handler_logs" {
  name              = "/aws/lambda/${aws_lambda_function.rollback_handler.function_name}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "callback_handler_logs" {
  name              = "/aws/lambda/${aws_lambda_function.callback_handler.function_name}"
  retention_in_days = 30
}
