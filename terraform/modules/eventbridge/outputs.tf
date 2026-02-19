output "bus_name" {
  description = "EventBridge event bus name"
  value       = aws_cloudwatch_event_bus.migration.name
}

output "bus_arn" {
  description = "EventBridge event bus ARN"
  value       = aws_cloudwatch_event_bus.migration.arn
}

output "dlq_url" {
  description = "EventBridge DLQ URL"
  value       = aws_sqs_queue.eventbridge_dlq.url
}
