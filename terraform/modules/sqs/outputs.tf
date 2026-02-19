output "queue_url" {
  description = "SQS queue URL"
  value       = aws_sqs_queue.migration_requests.url
}

output "queue_arn" {
  description = "SQS queue ARN"
  value       = aws_sqs_queue.migration_requests.arn
}

output "dlq_url" {
  description = "SQS Dead Letter Queue URL"
  value       = aws_sqs_queue.migration_requests_dlq.url
}

output "dlq_arn" {
  description = "SQS Dead Letter Queue ARN"
  value       = aws_sqs_queue.migration_requests_dlq.arn
}
