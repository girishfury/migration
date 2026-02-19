output "sqs_queue_url" {
  description = "SQS queue URL for migration requests"
  value       = module.sqs.queue_url
}

output "sqs_queue_arn" {
  description = "SQS queue ARN"
  value       = module.sqs.queue_arn
}

output "sqs_dlq_url" {
  description = "SQS Dead Letter Queue URL"
  value       = module.sqs.dlq_url
}

output "eventbridge_bus_name" {
  description = "EventBridge custom event bus name"
  value       = module.eventbridge.bus_name
}

output "eventbridge_bus_arn" {
  description = "EventBridge custom event bus ARN"
  value       = module.eventbridge.bus_arn
}

output "dynamodb_table_name" {
  description = "DynamoDB table name for migration state"
  value       = module.dynamodb.table_name
}

output "dynamodb_table_arn" {
  description = "DynamoDB table ARN"
  value       = module.dynamodb.table_arn
}

output "stepfunctions_state_machine_arn" {
  description = "Step Functions state machine ARN"
  value       = module.stepfunctions.state_machine_arn
}

output "stepfunctions_state_machine_name" {
  description = "Step Functions state machine name"
  value       = module.stepfunctions.state_machine_name
}

output "lambda_ingress_handler_arn" {
  description = "Ingress Handler Lambda function ARN"
  value       = module.lambda.ingress_handler_lambda_arn
}

output "lambda_validate_input_arn" {
  description = "Validate Input Lambda function ARN"
  value       = module.lambda.validate_input_lambda_arn
}

output "lambda_prepare_source_arn" {
  description = "Prepare Source Lambda function ARN"
  value       = module.lambda.prepare_source_lambda_arn
}

output "lambda_trigger_migration_arn" {
  description = "Trigger Migration Lambda function ARN"
  value       = module.lambda.trigger_migration_lambda_arn
}

output "lambda_verify_migration_arn" {
  description = "Verify Migration Lambda function ARN"
  value       = module.lambda.verify_migration_lambda_arn
}

output "lambda_finalize_cutover_arn" {
  description = "Finalize Cutover Lambda function ARN"
  value       = module.lambda.finalize_cutover_lambda_arn
}

output "lambda_rollback_handler_arn" {
  description = "Rollback Handler Lambda function ARN"
  value       = module.lambda.rollback_handler_lambda_arn
}

output "lambda_callback_handler_arn" {
  description = "Callback Handler Lambda function ARN"
  value       = module.lambda.callback_handler_lambda_arn
}

output "api_gateway_endpoint_url" {
  description = "API Gateway endpoint URL for migration requests"
  value       = module.api_gateway.endpoint_url
}

output "api_gateway_invoke_arn" {
  description = "API Gateway invoke ARN"
  value       = module.api_gateway.invoke_arn
}

output "sns_notification_topic_arn" {
  description = "SNS topic ARN for migration notifications"
  value       = aws_sns_topic.migration_notifications.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for migration logs"
  value       = aws_cloudwatch_log_group.migration_logs.name
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards:name=${aws_cloudwatch_dashboard.migration_dashboard.dashboard_name}"
}

output "kms_keys" {
  description = "KMS key information"
  value = {
    lambda_key_id      = module.kms.lambda_key_id
    sqs_key_id         = module.kms.sqs_key_id
    dynamodb_key_id    = module.kms.dynamodb_key_id
    sns_key_id         = module.kms.sns_key_id
    logs_key_arn       = module.kms.logs_key_arn
  }
  sensitive = true
}
