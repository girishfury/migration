terraform {
  backend "s3" {
    bucket         = "REPLACE_WITH_YOUR_BUCKET"
    key            = "event-driven-migration/terraform-prod.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

# Deploy prod environment
environment  = "prod"
region       = "us-east-1"
project_name = "migration-orchestration"

# Lambda configuration
lambda_timeout = 600
lambda_memory  = 1024

# Enable X-Ray tracing
enable_xray = true

# CloudWatch log retention
log_retention_days = 60

# Tags
tags = {
  Environment = "production"
  Owner       = "Platform Team"
  Project     = "Migration Orchestration"
  ManagedBy   = "Terraform"
  CostCenter  = "Engineering"
}
