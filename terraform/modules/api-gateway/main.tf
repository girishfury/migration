variable "environment" {
  type = string
}

variable "project_name" {
  type = string
}

variable "sqs_queue_url" {
  type = string
}

variable "ingress_handler_arn" {
  type = string
}

variable "ingress_handler_role_arn" {
  type = string
}

# REST API
resource "aws_apigatewayv2_api" "migration_api" {
  name          = "${var.project_name}-migration-api"
  protocol_type = "HTTP"
  
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["*"]
  }

  tags = {
    Name = "${var.project_name}-migration-api"
  }
}

# API Stage
resource "aws_apigatewayv2_stage" "migration_api_stage" {
  api_id      = aws_apigatewayv2_api.migration_api.id
  name        = var.environment
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      error          = "$context.error.message"
      errorType      = "$context.error.messageString"
    })
  }

  default_route_settings {
    logging_level            = "INFO"
    data_trace_enabled       = true
    throttle_burst_limit     = 100
    throttle_rate_limit      = 50
  }
}

# API Integration with Lambda
resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id           = aws_apigatewayv2_api.migration_api.id
  integration_type = "AWS_PROXY"
  integration_method = "POST"
  payload_format_version = "2.0"
  target = aws_lambda_function.ingress_handler_proxy.invoke_arn
}

# Lambda proxy function for API Gateway
resource "aws_lambda_function" "ingress_handler_proxy" {
  filename      = data.archive_file.ingress_handler_proxy.output_path
  function_name = "${var.project_name}-ingress-handler-proxy"
  role          = var.ingress_handler_role_arn
  handler       = "index.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60
  memory_size   = 256

  environment {
    variables = {
      SQS_QUEUE_URL = var.sqs_queue_url
    }
  }

  depends_on = [data.archive_file.ingress_handler_proxy]
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingress_handler_proxy.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.migration_api.execution_arn}/*/*"
}

# API Route - POST /migrations
resource "aws_apigatewayv2_route" "create_migration" {
  api_id    = aws_apigatewayv2_api.migration_api.id
  route_key = "POST /migrations"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# API Route - POST /migrations/test
resource "aws_apigatewayv2_route" "test_migration" {
  api_id    = aws_apigatewayv2_api.migration_api.id
  route_key = "POST /migrations/test"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway_logs" {
  name              = "/aws/apigateway/${var.project_name}"
  retention_in_days = 30
}

# Data source for proxy handler archive
data "archive_file" "ingress_handler_proxy" {
  type        = "zip"
  output_path = "${path.module}/.terraform/ingress_handler_proxy.zip"
  
  source {
    content  = <<-EOT
import json
import boto3
import os

sqs = boto3.client('sqs')

def lambda_handler(event, context):
    queue_url = os.environ['SQS_QUEUE_URL']
    
    try:
        body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(body)
        )
        
        return {
            'statusCode': 202,
            'body': json.dumps({
                'message': 'Migration request accepted',
                'messageId': response['MessageId']
            }),
            'headers': {
                'Content-Type': 'application/json'
            }
        }
    except Exception as e:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': str(e)
            }),
            'headers': {
                'Content-Type': 'application/json'
            }
        }
EOT
    filename = "index.py"
  }
}
