output "ingress_handler_lambda_arn" {
  description = "Ingress Handler Lambda ARN"
  value       = aws_lambda_function.ingress_handler.arn
}

output "validate_input_lambda_arn" {
  description = "Validate Input Lambda ARN"
  value       = aws_lambda_function.validate_input.arn
}

output "prepare_source_lambda_arn" {
  description = "Prepare Source Lambda ARN"
  value       = aws_lambda_function.prepare_source.arn
}

output "trigger_migration_lambda_arn" {
  description = "Trigger Migration Lambda ARN"
  value       = aws_lambda_function.trigger_migration.arn
}

output "verify_migration_lambda_arn" {
  description = "Verify Migration Lambda ARN"
  value       = aws_lambda_function.verify_migration.arn
}

output "finalize_cutover_lambda_arn" {
  description = "Finalize Cutover Lambda ARN"
  value       = aws_lambda_function.finalize_cutover.arn
}

output "rollback_handler_lambda_arn" {
  description = "Rollback Handler Lambda ARN"
  value       = aws_lambda_function.rollback_handler.arn
}

output "callback_handler_lambda_arn" {
  description = "Callback Handler Lambda ARN"
  value       = aws_lambda_function.callback_handler.arn
}
