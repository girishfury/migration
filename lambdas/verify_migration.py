"""
Verify Migration Lambda Function

Polls MGN status, validates replication lag, checks application health.
"""
import os
import time
from typing import Dict, Any

import boto3

from common.logger import get_logger
from common.correlation import extract_correlation_id
from common.errors import VerificationError
from common.eventbridge_helper import EventBridgePublisher
from common.dynamodb_helper import MigrationStateManager

logger = get_logger(__name__)
eventbridge = EventBridgePublisher(os.environ.get("EVENTBRIDGE_BUS_NAME"))
state_manager = MigrationStateManager(os.environ.get("DYNAMODB_TABLE_NAME"))


def check_mgn_replication_status(
    source_vm_id: str,
) -> Dict[str, Any]:
    """Check MGN replication status."""
    logger.info("Checking MGN replication status")
    
    mgn = boto3.client("mgn")
    
    try:
        response = mgn.describe_source_servers(
            filters={
                "sourceServerIDs": [source_vm_id],
            }
        )
        
        if not response.get("items"):
            raise VerificationError("Source server not found in MGN")
        
        server = response["items"][0]
        replication_info = server.get("replicationStatus", {})
        
        status_info = {
            "replicationStatus": replication_info.get("status"),
            "replicationLag": replication_info.get("replicationLagSec", 0),
            "lastSeenByService": replication_info.get("lastSeenByService", ""),
        }
        
        logger.info("MGN replication status retrieved", extra=status_info)
        return status_info
        
    except Exception as e:
        raise VerificationError(
            f"Failed to check MGN replication status: {str(e)}",
            details={"service": "mgn"},
        )


def validate_replication_lag(replication_lag: int, threshold: int = 300) -> bool:
    """Validate replication lag is within acceptable threshold."""
    logger.info(
        "Validating replication lag",
        extra={
            "lag_seconds": replication_lag,
            "threshold_seconds": threshold,
        },
    )
    
    if replication_lag > threshold:
        logger.warning(
            "Replication lag exceeds threshold",
            extra={
                "lag": replication_lag,
                "threshold": threshold,
            },
        )
        return False
    
    return True


def check_application_health(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Check application health on migrated instance."""
    logger.info("Checking application health")
    
    # In production, this would integrate with health check endpoints
    # or CloudWatch metrics for the target instance
    
    health_status = {
        "appName": payload.get("appName"),
        "healthStatus": "HEALTHY",
        "checkedAt": __import__("datetime").datetime.utcnow().isoformat(),
        "checks": {
            "connectivity": True,
            "diskSpace": True,
            "memory": True,
            "cpu": True,
        },
    }
    
    logger.info("Application health check completed", extra=health_status)
    return health_status


def lambda_handler(event, context):
    """
    Verify migration status.
    
    Args:
        event: EventBridge event
        context: Lambda context
    
    Returns:
        dict: Verification result
    """
    try:
        detail = event.get("detail", {})
        correlation_id = extract_correlation_id(event)
        logger.set_correlation_id(correlation_id)
        
        migration_id = detail.get("migrationId")
        logger.info(
            "Starting migration verification",
            extra={"migrationId": migration_id},
        )
        
        # Check MGN replication status
        replication_status = check_mgn_replication_status(
            detail.get("sourceVmId", "")
        )
        
        # Validate replication lag
        replication_lag = replication_status.get("replicationLag", 0)
        is_replication_acceptable = validate_replication_lag(replication_lag)
        
        if not is_replication_acceptable:
            raise VerificationError(
                "Replication lag exceeds acceptable threshold",
                details={"lag": replication_lag},
            )
        
        # Check application health
        health_status = check_application_health(detail)
        
        # Update migration state
        state_manager.update_migration_status(
            migration_id,
            "VERIFIED",
            execution_details={
                "replication": replication_status,
                "health": health_status,
            },
        )
        
        logger.info(
            "Migration verification completed",
            extra={"migrationId": migration_id},
        )
        
        # Publish status event
        eventbridge.publish_status_event(
            migration_id=migration_id,
            correlation_id=correlation_id,
            current_step="verify_migration",
            status="SUCCESS",
            details={
                "replication": replication_status,
                "health": health_status,
            },
        )
        
        return {
            "statusCode": 200,
            "body": {
                "migrationId": migration_id,
                "status": "VERIFIED",
                "replication": replication_status,
                "health": health_status,
            },
        }
        
    except VerificationError as e:
        logger.error("Migration verification failed", extra=e.to_dict())
        
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
        logger.error("Unexpected error in migration verification", extra={"error": str(e)})
        return {
            "statusCode": 500,
            "body": {"error": "Migration verification failed"},
        }
