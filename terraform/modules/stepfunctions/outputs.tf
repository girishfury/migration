output "state_machine_arn" {
  description = "Step Functions State Machine ARN"
  value       = aws_sfn_state_machine.migration_orchestration.arn
}

output "state_machine_name" {
  description = "Step Functions State Machine Name"
  value       = aws_sfn_state_machine.migration_orchestration.name
}
