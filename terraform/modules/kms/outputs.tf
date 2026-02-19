output "lambda_key_id" {
  description = "Lambda KMS key ID"
  value       = aws_kms_key.lambda.id
}

output "lambda_key_arn" {
  description = "Lambda KMS key ARN"
  value       = aws_kms_key.lambda.arn
}

output "sqs_key_id" {
  description = "SQS KMS key ID"
  value       = aws_kms_key.sqs.id
}

output "sqs_key_arn" {
  description = "SQS KMS key ARN"
  value       = aws_kms_key.sqs.arn
}

output "dynamodb_key_id" {
  description = "DynamoDB KMS key ID"
  value       = aws_kms_key.dynamodb.id
}

output "dynamodb_key_arn" {
  description = "DynamoDB KMS key ARN"
  value       = aws_kms_key.dynamodb.arn
}

output "sns_key_id" {
  description = "SNS KMS key ID"
  value       = aws_kms_key.sns.id
}

output "sns_key_arn" {
  description = "SNS KMS key ARN"
  value       = aws_kms_key.sns.arn
}

output "logs_key_arn" {
  description = "CloudWatch Logs KMS key ARN"
  value       = aws_kms_key.logs.arn
}
