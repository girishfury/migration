output "lambda_execution_role_arn" {
  description = "Lambda execution role ARN"
  value       = aws_iam_role.lambda_execution.arn
}

output "stepfunctions_execution_role_arn" {
  description = "Step Functions execution role ARN"
  value       = aws_iam_role.stepfunctions_execution.arn
}

output "api_gateway_execution_role_arn" {
  description = "API Gateway execution role ARN"
  value       = aws_iam_role.api_gateway_execution.arn
}
