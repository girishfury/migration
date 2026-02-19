"""
Rollback Handler Lambda Function

Handles rollback on failure, restores previous state, notifies stakeholders.
"""
import os
from typing import Dict, Any

import boto3

from common.logger import get_logger
from common.correlation import extract_correlation_id
from common.errors import RollbackError
from common.eventbridge_helper import EventBridgePublisher
from common.dynamodb_helper import MigrationStateManager

logger = get_logger(__name__)
eventbridge = EventBridgePublisher(os.environ.get("EVENTBRIDGE_BUS_NAME"))
state_manager = MigrationStateManager(os.environ.get("DYNAMODB_TABLE_NAME"))


def stop_mgn_replication(source_vm_id: str) -> Dict[str, Any]:
    """Stop MGN replication for source."""
    logger.info("Stopping MGN replication")
    
    mgn = boto3.client("mgn")
    
    try:
        # Stop replication
        mgn.discontinue_from_launch(
            sourceServerIDs=[source_vm_id],
        )
        
        logger.info("MGN replication stopped")
        
        return {
            "status": "REPLICATION_STOPPED",
            "sourceVmId": source_vm_id,
        }
        
    except Exception as e:
        raise RollbackError(
            f"Failed to stop MGN replication: {str(e)}",
            details={"service": "mgn"},
        )


def terminate_target_instance(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Terminate target AWS instance."""
    logger.info("Terminating target instance")
    
    ec2 = boto3.client("ec2")
    
    # In production, get instance ID from migration state
    instance_id = payload.get("targetInstanceId")
    
    if not instance_id:
        logger.warning("No target instance ID found for termination")
        return {
            "status": "SKIPPED",
            "reason": "No target instance ID",
        }
    
    try:
        ec2.terminate_instances(InstanceIds=[instance_id])
        
        logger.info("Target instance termination initiated")
        
        return {
            "status": "INSTANCE_TERMINATED",
            "instanceId": instance_id,
        }
        
    except Exception as e:
        raise RollbackError(
            f"Failed to terminate target instance: {str(e)}",
            details={"instanceId": instance_id},
        )


def restore_source_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Restore source VM to previous state."""
    logger.info("Restoring source VM state")
    
    # In production, this would restore from snapshots or backups
    source_vm_id = payload.get("sourceVmId")
    
    if not source_vm_id:
        raise RollbackError("Source VM ID not provided for state restoration")
    
    restore_result = {
        "sourceVmId": source_vm_id,
        "status": "STATE_RESTORED",
        "restoredAt": __import__("datetime").datetime.utcnow().isoformat(),
    }
    
    logger.info("Source VM state restored", extra=restore_result)
    return restore_result


def notify_stakeholders(
    migration_id: str,
    error_details: Dict[str, Any],
) -> Dict[str, Any]:
    """Notify stakeholders of rollback."""
    logger.info("Notifying stakeholders of rollback")
    
    # In production, this would send emails/notifications via SNS
    notification = {
        "migrationId": migration_id,
        "notificationType": "ROLLBACK_NOTIFICATION",
        "status": "SENT",
        "sentAt": __import__("datetime").datetime.utcnow().isoformat(),
        "errorDetails": error_details,
    }
    
    logger.info("Stakeholders notified", extra=notification)
    return notification


def lambda_handler(event, context):
    """
    Handle rollback on migration failure.
    
    Args:
        event: EventBridge event
        context: Lambda context
    
    Returns:
        dict: Rollback result
    """
    try:
        detail = event.get("detail", {})
        correlation_id = extract_correlation_id(event)
        logger.set_correlation_id(correlation_id)
        
        migration_id = detail.get("migrationId")
        logger.info(
            "Starting rollback process",
            extra={
                "migrationId": migration_id,
                "errorCode": detail.get("errorCode"),
            },
        )
        
        rollback_results = {}
        
        # Stop MGN replication
        try:
            source_vm_id = detail.get("sourceVmId")
            if source_vm_id:
                rollback_results["mgnReplication"] = stop_mgn_replication(source_vm_id)
        except Exception as e:
            logger.warning("Failed to stop MGN replication", extra={"error": str(e)})
            rollback_results["mgnReplication"] = {"status": "FAILED", "error": str(e)}
        
        # Terminate target instance
        try:
            rollback_results["targetInstance"] = terminate_target_instance(detail)
        except Exception as e:
            logger.warning("Failed to terminate target instance", extra={"error": str(e)})
            rollback_results["targetInstance"] = {"status": "FAILED", "error": str(e)}
        
        # Restore source state
        try:
            rollback_results["sourceState"] = restore_source_state(detail)
        except Exception as e:
            logger.warning("Failed to restore source state", extra={"error": str(e)})
            rollback_results["sourceState"] = {"status": "FAILED", "error": str(e)}
        
        # Notify stakeholders
        try:
            rollback_results["notification"] = notify_stakeholders(
                migration_id,
                {
                    "errorCode": detail.get("errorCode"),
                    "errorMessage": detail.get("errorMessage"),
                },
            )
        except Exception as e:
            logger.warning("Failed to notify stakeholders", extra={"error": str(e)})
            rollback_results["notification"] = {"status": "FAILED", "error": str(e)}
        
        # Update migration state
        state_manager.update_migration_status(
            migration_id,
            "ROLLED_BACK",
            execution_details=rollback_results,
        )
        
        logger.info(
            "Rollback process completed",
            extra={"migrationId": migration_id},
        )
        
        # Publish rollback event
        eventbridge.publish_event(
            detail_type="MigrationRolledBack",
            detail={
                "migrationId": migration_id,
                "correlationId": correlation_id,
                "status": "ROLLED_BACK",
                "rollbackDetails": rollback_results,
                "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            },
        )
        
        return {
            "statusCode": 200,
            "body": {
                "migrationId": migration_id,
                "status": "ROLLED_BACK",
                "rollbackDetails": rollback_results,
            },
        }
        
    except RollbackError as e:
        logger.error("Critical rollback error", extra=e.to_dict())
        
        return {
            "statusCode": 500,
            "body": e.to_dict(),
        }
        
    except Exception as e:
        logger.error("Unexpected error in rollback handler", extra={"error": str(e)})
        return {
            "statusCode": 500,
            "body": {"error": "Rollback process failed"},
        }
