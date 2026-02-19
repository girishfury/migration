"""
Ingress Handler Lambda Function

Receives SQS messages, validates schema, publishes to EventBridge with correlation ID.
"""
import json
import os
from typing import Dict, Any

import boto3
from jsonschema import validate, ValidationError as JsonSchemaError

from common.logger import get_logger
from common.correlation import extract_correlation_id, inject_correlation_id
from common.errors import ValidationError
from common.eventbridge_helper import EventBridgePublisher

logger = get_logger(__name__)
eventbridge = EventBridgePublisher(os.environ.get("EVENTBRIDGE_BUS_NAME"))

# Load schema
with open("schemas/migration_payload.json") as f:
    MIGRATION_SCHEMA = json.load(f)


def validate_message(message: Dict[str, Any]) -> None:
    """Validate message against schema."""
    try:
        validate(instance=message, schema=MIGRATION_SCHEMA)
    except JsonSchemaError as e:
        raise ValidationError(
            f"Invalid migration payload: {e.message}",
            details={"path": str(e.path), "message": e.message},
        )


def lambda_handler(event, context):
    """
    Handler for SQS events.
    
    Args:
        event: SQS event
        context: Lambda context
    
    Returns:
        dict: Processing result
    """
    try:
        logger.info("Ingress handler started")
        
        # Process SQS records
        results = {
            "successful": [],
            "failed": [],
        }
        
        for record in event.get("Records", []):
            try:
                # Parse message body
                body = json.loads(record["body"])
                
                # Extract or generate correlation ID
                correlation_id = extract_correlation_id(body)
                logger.set_correlation_id(correlation_id)
                
                logger.info(
                    "Processing migration",
                    extra={"migrationId": body.get("migrationId")},
                )
                
                # Validate against schema
                validate_message(body)
                
                # Inject correlation ID into event
                body = inject_correlation_id(body, correlation_id)
                
                # Publish to EventBridge
                event_id = eventbridge.publish_event(
                    detail_type="MigrationRequested",
                    detail=body,
                    source="migration.ingress",
                )
                
                logger.info(
                    "Event published to EventBridge",
                    extra={
                        "eventId": event_id,
                        "migrationId": body.get("migrationId"),
                    },
                )
                
                results["successful"].append(
                    {
                        "messageId": record["messageId"],
                        "eventId": event_id,
                        "migrationId": body.get("migrationId"),
                    }
                )
                
            except ValidationError as e:
                logger.error(
                    "Validation failed",
                    extra=e.to_dict(),
                )
                results["failed"].append(
                    {
                        "messageId": record["messageId"],
                        "error": e.to_dict(),
                    }
                )
            except Exception as e:
                logger.error(
                    "Unexpected error processing message",
                    extra={"error": str(e)},
                )
                results["failed"].append(
                    {
                        "messageId": record["messageId"],
                        "error": str(e),
                    }
                )
        
        logger.info(
            "Ingress handler completed",
            extra={
                "successful": len(results["successful"]),
                "failed": len(results["failed"]),
            },
        )
        
        return {
            "statusCode": 200,
            "body": json.dumps(results),
        }
        
    except Exception as e:
        logger.error("Critical error in ingress handler", extra={"error": str(e)})
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }
