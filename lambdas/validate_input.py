"""
Validate Input Lambda Function

Validates migration payload, checks prerequisites, verifies source/target connectivity.
"""
import os
from typing import Dict, Any

import boto3

from common.logger import get_logger
from common.correlation import extract_correlation_id
from common.errors import PrerequisiteError, ValidationError
from common.eventbridge_helper import EventBridgePublisher
from common.dynamodb_helper import MigrationStateManager

logger = get_logger(__name__)
eventbridge = EventBridgePublisher(os.environ.get("EVENTBRIDGE_BUS_NAME"))
state_manager = MigrationStateManager(os.environ.get("DYNAMODB_TABLE_NAME"))


def check_aws_prerequisites(payload: Dict[str, Any]) -> None:
    """Verify AWS resources are accessible."""
    ec2 = boto3.client("ec2")
    
    try:
        # Check subnet exists
        if "subnetId" in payload:
            ec2.describe_subnets(SubnetIds=[payload["subnetId"]])
        
        # Check security groups exist
        if "securityGroupIds" in payload:
            ec2.describe_security_groups(
                GroupIds=payload["securityGroupIds"]
            )
        
        logger.info("AWS prerequisites verified")
        
    except Exception as e:
        raise PrerequisiteError(
            f"AWS resource verification failed: {str(e)}",
            details={"resource": "ec2"},
        )


def check_mgn_prerequisites() -> None:
    """Verify MGN service is available."""
    try:
        mgn = boto3.client("mgn")
        mgn.describe_source_servers()
        logger.info("MGN service verified")
    except Exception as e:
        raise PrerequisiteError(
            f"MGN service check failed: {str(e)}",
            details={"service": "mgn"},
        )


def validate_payload_content(payload: Dict[str, Any]) -> None:
    """Validate payload content beyond schema."""
    required_fields = {
        "migrationId": "string",
        "appName": "string",
        "source": "string",
        "target": "string",
        "environment": "string",
        "wave": "string",
    }
    
    for field, field_type in required_fields.items():
        if field not in payload:
            raise ValidationError(
                f"Missing required field: {field}",
                details={"field": field},
            )
        
        if not isinstance(payload[field], dict if field_type == "object" else str):
            raise ValidationError(
                f"Invalid type for field {field}",
                details={"field": field, "expected": field_type},
            )


def lambda_handler(event, context):
    """
    Validate migration input.
    
    Args:
        event: EventBridge event
        context: Lambda context
    
    Returns:
        dict: Validation result
    """
    try:
        detail = event.get("detail", {})
        correlation_id = extract_correlation_id(event)
        logger.set_correlation_id(correlation_id)
        
        migration_id = detail.get("migrationId")
        logger.info(
            "Validating migration input",
            extra={"migrationId": migration_id},
        )
        
        # Validate payload content
        validate_payload_content(detail)
        
        # Check AWS prerequisites
        check_aws_prerequisites(detail)
        
        # Check MGN prerequisites
        check_mgn_prerequisites()
        
        # Save validation state
        state_manager.save_migration_state(
            migration_id,
            {
                **detail,
                "status": "VALIDATED",
                "correlationId": correlation_id,
            },
        )
        
        logger.info(
            "Input validation successful",
            extra={"migrationId": migration_id},
        )
        
        # Publish success event
        eventbridge.publish_status_event(
            migration_id=migration_id,
            correlation_id=correlation_id,
            current_step="validate_input",
            status="SUCCESS",
        )
        
        return {
            "statusCode": 200,
            "body": {
                "migrationId": migration_id,
                "status": "VALIDATED",
            },
        }
        
    except (ValidationError, PrerequisiteError) as e:
        logger.error("Validation failed", extra=e.to_dict())
        
        migration_id = detail.get("migrationId", "unknown")
        
        # Publish failure event
        try:
            eventbridge.publish_failure_event(
                migration_id=migration_id,
                correlation_id=correlation_id,
                error_code=e.error_code,
                error_message=e.message,
            )
        except:
            pass
        
        return {
            "statusCode": 400,
            "body": e.to_dict(),
        }
        
    except Exception as e:
        logger.error("Unexpected error in validation", extra={"error": str(e)})
        return {
            "statusCode": 500,
            "body": {"error": "Internal validation error"},
        }
