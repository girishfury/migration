variable "environment" {
  type = string
}

variable "project_name" {
  type = string
}

variable "stepfunctions_role_arn" {
  type = string
}

variable "validate_input_arn" {
  type = string
}

variable "prepare_source_arn" {
  type = string
}

variable "trigger_migration_arn" {
  type = string
}

variable "verify_migration_arn" {
  type = string
}

variable "finalize_cutover_arn" {
  type = string
}

variable "rollback_handler_arn" {
  type = string
}

variable "callback_handler_arn" {
  type = string
}

# Step Functions State Machine Definition
resource "aws_sfn_state_machine" "migration_orchestration" {
  name       = "${var.project_name}-migration-orchestration"
  role_arn   = var.stepfunctions_role_arn
  definition = jsonencode({
    Comment = "Migration Orchestration State Machine"
    StartAt = "ValidateInput"
    States = {
      ValidateInput = {
        Type     = "Task"
        Resource = var.validate_input_arn
        Next     = "PrepareSource"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "MigrationFailed"
            ResultPath  = "$.error"
          }
        ]
        Retry = [
          {
            ErrorEquals = ["States.TaskFailed"]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2
          }
        ]
      }

      PrepareSource = {
        Type     = "Task"
        Resource = var.prepare_source_arn
        Next     = "TriggerMigration"
        TimeoutSeconds = 1800
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "MigrationFailed"
            ResultPath  = "$.error"
          }
        ]
        Retry = [
          {
            ErrorEquals = ["States.TaskFailed"]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2
          }
        ]
      }

      TriggerMigration = {
        Type     = "Task"
        Resource = var.trigger_migration_arn
        Next     = "WaitBeforeVerification"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "Rollback"
            ResultPath  = "$.error"
          }
        ]
      }

      WaitBeforeVerification = {
        Type    = "Wait"
        Seconds = 30
        Next    = "VerifyMigration"
      }

      VerifyMigration = {
        Type     = "Task"
        Resource = var.verify_migration_arn
        Next     = "CheckVerificationStatus"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "Rollback"
            ResultPath  = "$.error"
          }
        ]
      }

      CheckVerificationStatus = {
        Type = "Choice"
        Choices = [
          {
            Variable      = "$.readyForCutover"
            BooleanEquals = true
            Next          = "FinalizeCutover"
          }
        ]
        Default = "WaitAndRetryVerification"
      }

      WaitAndRetryVerification = {
        Type    = "Wait"
        Seconds = 60
        Next    = "VerifyMigrationWithBackoff"
      }

      VerifyMigrationWithBackoff = {
        Type     = "Task"
        Resource = var.verify_migration_arn
        Next     = "CheckVerificationStatus"
        TimeoutSeconds = 600
      }

      FinalizeCutover = {
        Type     = "Task"
        Resource = var.finalize_cutover_arn
        Next     = "MigrationSucceeded"
        TimeoutSeconds = 1800
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "Rollback"
            ResultPath  = "$.error"
          }
        ]
      }

      MigrationSucceeded = {
        Type     = "Task"
        Resource = var.callback_handler_arn
        Next     = "Success"
        Parameters = {
          "status.$"     = "$$.State.Status"
          "detail.$"     = "$.payload"
          "jobId.$"      = "$.jobId"
          "jobStatus.$"  = "$.jobStatus"
        }
      }

      Rollback = {
        Type     = "Task"
        Resource = var.rollback_handler_arn
        Next     = "MigrationFailed"
      }

      MigrationFailed = {
        Type     = "Task"
        Resource = var.callback_handler_arn
        Next     = "Failure"
        Parameters = {
          "status"       = "FAILED"
          "detail.$"     = "$.payload"
          "error.$"      = "$.error"
        }
      }

      Success = {
        Type = "Succeed"
      }

      Failure = {
        Type = "Fail"
        Error = "MigrationFailed"
        Cause = "Migration orchestration failed"
      }
    }
  })

  logging_configuration {
    log_destination        = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/states/${var.project_name}"
    include_execution_data = true
    level                  = "ALL"
  }

  depends_on = [
    aws_cloudwatch_log_group.stepfunctions_logs
  ]
}

# CloudWatch Log Group for Step Functions
resource "aws_cloudwatch_log_group" "stepfunctions_logs" {
  name              = "/aws/states/${var.project_name}"
  retention_in_days = 30
}

# Data sources
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
