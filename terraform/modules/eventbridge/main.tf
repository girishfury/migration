variable "environment" {
  type = string
}

variable "project_name" {
  type = string
}

variable "stepfunctions_arn" {
  type = string
}

# EventBridge Custom Event Bus
resource "aws_cloudwatch_event_bus" "migration" {
  name = "${var.project_name}-event-bus"

  tags = {
    Name = "${var.project_name}-event-bus"
  }
}

# EventBridge Rule for Ingress Events
resource "aws_cloudwatch_event_rule" "migration_ingress" {
  name           = "${var.project_name}-ingress-rule"
  event_bus_name = aws_cloudwatch_event_bus.migration.name
  description    = "Route migration ingress events to Step Functions"

  event_pattern = jsonencode({
    source      = ["migration.ingress"]
    detail-type = ["Migration Request Received"]
  })
}

# EventBridge Target - Step Functions
resource "aws_cloudwatch_event_target" "stepfunctions" {
  rule           = aws_cloudwatch_event_rule.migration_ingress.name
  event_bus_name = aws_cloudwatch_event_bus.migration.name
  target_id      = "StepFunctionsTarget"
  arn            = var.stepfunctions_arn
  role_arn       = aws_iam_role.eventbridge_stepfunctions_role.arn

  dead_letter_config {
    arn = aws_sqs_queue.eventbridge_dlq.arn
  }

  input_transformer {
    input_paths_map = {
      detail = "$.detail"
    }
    input_template = jsonencode({
      detail = "<detail>"
    })
  }
}

# EventBridge Rule for Success Events
resource "aws_cloudwatch_event_rule" "migration_success" {
  name           = "${var.project_name}-success-rule"
  event_bus_name = aws_cloudwatch_event_bus.migration.name
  description    = "Route migration success events"

  event_pattern = jsonencode({
    source      = ["migration.orchestration"]
    detail-type = ["Migration Completed"]
    status      = ["SUCCESS"]
  })
}

# EventBridge Rule for Failure Events
resource "aws_cloudwatch_event_rule" "migration_failure" {
  name           = "${var.project_name}-failure-rule"
  event_bus_name = aws_cloudwatch_event_bus.migration.name
  description    = "Route migration failure events"

  event_pattern = jsonencode({
    source      = ["migration.orchestration"]
    detail-type = ["Migration Completed"]
    status      = ["FAILED"]
  })
}

# DLQ for EventBridge
resource "aws_sqs_queue" "eventbridge_dlq" {
  name                      = "${var.project_name}-eventbridge-dlq"
  message_retention_seconds = 1209600

  tags = {
    Name = "${var.project_name}-eventbridge-dlq"
  }
}

# IAM Role for EventBridge to invoke Step Functions
resource "aws_iam_role" "eventbridge_stepfunctions_role" {
  name = "${var.project_name}-eventbridge-stepfunctions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "eventbridge_stepfunctions_policy" {
  name = "${var.project_name}-eventbridge-stepfunctions-policy"
  role = aws_iam_role.eventbridge_stepfunctions_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = var.stepfunctions_arn
      }
    ]
  })
}
