variable "environment" {
  type = string
}

variable "project_name" {
  type = string
}

variable "kms_key_id" {
  type = string
}

# SQS Queue for migration requests
resource "aws_sqs_queue" "migration_requests" {
  name                       = "${var.project_name}-migration-requests"
  visibility_timeout_seconds = 900
  message_retention_seconds  = 1209600  # 14 days
  kms_master_key_id          = var.kms_key_id

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.migration_requests_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name = "${var.project_name}-migration-requests"
  }
}

# Dead Letter Queue
resource "aws_sqs_queue" "migration_requests_dlq" {
  name                      = "${var.project_name}-migration-requests-dlq"
  message_retention_seconds = 1209600  # 14 days
  kms_master_key_id         = var.kms_key_id

  tags = {
    Name = "${var.project_name}-migration-requests-dlq"
  }
}

# SQS Queue Policy
resource "aws_sqs_queue_policy" "migration_requests" {
  queue_url = aws_sqs_queue.migration_requests.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action   = "sqs:*"
        Resource = aws_sqs_queue.migration_requests.arn
      },
      {
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.migration_requests.arn
      }
    ]
  })
}

# CloudWatch Alarms for DLQ
resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  alarm_name          = "${var.project_name}-dlq-messages-alarm"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 1
  alarm_description   = "Alert when DLQ has messages"

  dimensions = {
    QueueName = aws_sqs_queue.migration_requests_dlq.name
  }
}
