"""
Trigger Migration Lambda Function

Calls AWS MGN API to start test/cutover, integrates with CMF for wave management.
"""
import os
from typing import Dict, Any

import boto3

from common.logger import get_logger
from common.correlation import extract_correlation_id
from common.errors import MigrationExecutionError
from common.eventbridge_helper import EventBridgePublisher
from common.dynamodb_helper import MigrationStateManager

logger = get_logger(__name__)
eventbridge = EventBridgePublisher(os.environ.get("EVENTBRIDGE_BUS_NAME"))
state_manager = MigrationStateManager(os.environ.get("DYNAMODB_TABLE_NAME"))


def trigger_mgn_test_launch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger MGN test launch."""
    logger.info("Triggering MGN test launch")
    
    mgn = boto3.client("mgn")
    
    try:
        # Start test launch
        response = mgn.start_test_launch(
            sourceServerIDs=[payload.get("sourceVmId", "")],
            tags=payload.get("tags", {}),
        )
        
        logger.info("MGN test launch initiated")
        
        return {
            "jobId": response.get("job", {}).get("jobID"),
            "status": "TEST_LAUNCH_INITIATED",
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        raise MigrationExecutionError(
            f"Failed to trigger MGN test launch: {str(e)}",
            details={"service": "mgn"},
        )


def trigger_mgn_cutover(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger MGN cutover."""
    logger.info("Triggering MGN cutover")
    
    mgn = boto3.client("mgn")
    
    try:
        # Start cutover
        response = mgn.start_cutover(
            sourceServerIDs=[payload.get("sourceVmId", "")],
            tags=payload.get("tags", {}),
        )
        
        logger.info("MGN cutover initiated")
        
        return {
            "jobId": response.get("job", {}).get("jobID"),
            "status": "CUTOVER_INITIATED",
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        raise MigrationExecutionError(
            f"Failed to trigger MGN cutover: {str(e)}",
            details={"service": "mgn"},
        )


def update_cmf_wave_status(
    payload: Dict[str, Any], status: str
) -> Dict[str, Any]:
    """Update CMF wave status."""
    logger.info("Updating CMF wave status")
    
    # In production, this would call CMF API
    # For now, simulate the update
    cmf_update = {
        "wave": payload.get("wave"),
        "appName": payload.get("appName"),
        "status": status,
        "updatedAt": __import__("datetime").datetime.utcnow().isoformat(),
    }
    
    logger.info("CMF wave status updated", extra=cmf_update)
    return cmf_update


def lambda_handler(event, context):
    """
    Trigger migration via MGN and CMF.
    
    Args:
        event: EventBridge event
        context: Lambda context
    
    Returns:
        dict: Migration trigger result
    """
    try:
        detail = event.get("detail", {})
        correlation_id = extract_correlation_id(event)
        logger.set_correlation_id(correlation_id)
        
        migration_id = detail.get("migrationId")
        logger.info(
            "Triggering migration",
            extra={"migrationId": migration_id},
        )
        
        # Determine migration type (test vs cutover)
        steps = detail.get("steps", [])
        is_test = "freeze" not in steps or len(steps) < 3
        
        # Trigger appropriate migration type
        if is_test:
            migration_result = trigger_mgn_test_launch(detail)
        else:
            migration_result = trigger_mgn_cutover(detail)
        
        # Update CMF wave status
        cmf_result = update_cmf_wave_status(
            detail,
            "IN_PROGRESS",
        )
        
        # Update migration state
        state_manager.update_migration_status(
            migration_id,
            "MIGRATION_IN_PROGRESS",
            execution_details={
                "mgn": migration_result,
                "cmf": cmf_result,
            },
        )
        
        logger.info(
            "Migration triggered successfully",
            extra={"migrationId": migration_id},
        )
        
        # Publish status event
        eventbridge.publish_status_event(
            migration_id=migration_id,
            correlation_id=correlation_id,
            current_step="trigger_migration",
            status="IN_PROGRESS",
            details={
                "mgn": migration_result,
                "cmf": cmf_result,
            },
        )
        
        return {
            "statusCode": 200,
            "body": {
                "migrationId": migration_id,
                "status": "MIGRATION_IN_PROGRESS",
                "mgn": migration_result,
                "cmf": cmf_result,
            },
        }
        
    except MigrationExecutionError as e:
        logger.error("Migration trigger failed", extra=e.to_dict())
        
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
            "statusCode": 500,
            "body": e.to_dict(),
        }
        
    except Exception as e:
        logger.error("Unexpected error triggering migration", extra={"error": str(e)})
        return {
            "statusCode": 500,
            "body": {"error": "Failed to trigger migration"},
        }
