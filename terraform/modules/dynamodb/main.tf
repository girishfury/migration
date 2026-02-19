variable "environment" {
  type = string
}

variable "project_name" {
  type = string
}

variable "kms_key_id" {
  type = string
}

# DynamoDB Table for Migration State
resource "aws_dynamodb_table" "migration_state" {
  name           = "${var.project_name}-migration-state"
  billing_mode   = "PAY_PER_REQUEST"  # On-demand billing
  hash_key       = "migrationId"
  stream_specification {
    stream_view_type = "NEW_AND_OLD_IMAGES"
  }

  attribute {
    name = "migrationId"
    type = "S"
  }

  attribute {
    name = "wave"
    type = "S"
  }

  attribute {
    name = "appName"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  # Global Secondary Index for querying by wave
  global_secondary_index {
    name            = "wave-status-index"
    hash_key        = "wave"
    range_key       = "status"
    projection_type = "ALL"
  }

  # Global Secondary Index for querying by app
  global_secondary_index {
    name            = "app-status-index"
    hash_key        = "appName"
    range_key       = "status"
    projection_type = "ALL"
  }

  # Global Secondary Index for querying by status
  global_secondary_index {
    name            = "status-timestamp-index"
    hash_key        = "status"
    range_key       = "updatedAt"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = "arn:aws:kms:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:key/${var.kms_key_id}"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-migration-state"
  }
}

# Data sources for current AWS account and region
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# CloudWatch Alarms for DynamoDB
resource "aws_cloudwatch_metric_alarm" "dynamodb_read_throttle" {
  alarm_name          = "${var.project_name}-dynamodb-read-throttle"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ReadThrottleEvents"
  namespace           = "AWS/DynamoDB"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Alert when DynamoDB read throttling occurs"

  dimensions = {
    TableName = aws_dynamodb_table.migration_state.name
  }
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_write_throttle" {
  alarm_name          = "${var.project_name}-dynamodb-write-throttle"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "WriteThrottleEvents"
  namespace           = "AWS/DynamoDB"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Alert when DynamoDB write throttling occurs"

  dimensions = {
    TableName = aws_dynamodb_table.migration_state.name
  }
}
