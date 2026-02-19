output "table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.migration_state.name
}

output "table_arn" {
  description = "DynamoDB table ARN"
  value       = aws_dynamodb_table.migration_state.arn
}

output "stream_arn" {
  description = "DynamoDB stream ARN"
  value       = aws_dynamodb_table.migration_state.stream_arn
}
