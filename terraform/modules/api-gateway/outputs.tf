output "endpoint_url" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.migration_api_stage.invoke_url
}

output "invoke_arn" {
  description = "API Gateway invoke ARN"
  value       = aws_apigatewayv2_api.migration_api.execution_arn
}
