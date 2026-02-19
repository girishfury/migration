terraform {
  backend "s3" {
    bucket         = "REPLACE_WITH_YOUR_BUCKET"
    key            = "event-driven-migration/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

# Deploy dev environment
environment  = "dev"
region       = "us-east-1"
project_name = "migration-orchestration"

# Lambda configuration
lambda_timeout = 300
lambda_memory  = 512

# Enable X-Ray tracing
enable_xray = true

# CloudWatch log retention
log_retention_days = 30

# Tags
tags = {
  Environment = "development"
  Owner       = "Platform Team"
  Project     = "Migration Orchestration"
  ManagedBy   = "Terraform"
}
