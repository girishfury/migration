variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming and tagging"
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "github_repository" {
  description = "GitHub repository for OIDC (owner/repo format)"
  type        = string
  default     = ""
}

variable "github_ref" {
  description = "GitHub reference for OIDC (branch or tag)"
  type        = string
  default     = "main"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 300
  validation {
    condition     = var.lambda_timeout > 0 && var.lambda_timeout <= 900
    error_message = "Lambda timeout must be between 1 and 900 seconds."
  }
}

variable "lambda_memory" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 512
  validation {
    condition     = contains([128, 256, 512, 1024, 1536, 2048, 2560, 3008], var.lambda_memory)
    error_message = "Lambda memory must be a valid value (128, 256, 512, 1024, 1536, 2048, 2560, 3008)."
  }
}

variable "sqs_visibility_timeout" {
  description = "SQS visibility timeout in seconds"
  type        = number
  default     = 900
}

variable "sqs_retention_period" {
  description = "SQS message retention period in seconds"
  type        = number
  default     = 1209600  # 14 days
}

variable "dynamodb_read_capacity" {
  description = "DynamoDB read capacity units (for on-demand, set to null)"
  type        = number
  default     = null
}

variable "dynamodb_write_capacity" {
  description = "DynamoDB write capacity units (for on-demand, set to null)"
  type        = number
  default     = null
}

variable "enable_vpc" {
  description = "Enable VPC for Lambda functions"
  type        = bool
  default     = false
}

variable "vpc_subnet_ids" {
  description = "VPC subnet IDs for Lambda functions"
  type        = list(string)
  default     = []
}

variable "vpc_security_group_ids" {
  description = "VPC security group IDs for Lambda functions"
  type        = list(string)
  default     = []
}

variable "enable_xray" {
  description = "Enable X-Ray tracing for Lambda functions"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid AWS value."
  }
}

variable "tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}
