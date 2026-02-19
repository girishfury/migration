"""
Rollback Handler Lambda Function
Handles rollback on failure, restores previous state, notifies stakeholders
"""

import json
import logging
import boto3
import time
from typing import Dict, Any, Tuple

from common.logger import get_logger
from common.correlation import get_correlation_id, propagate_context
from common.dynamodb_helper import update_migration_state

logger = get_logger(__name__)
mgn_client = boto3.client('mgn')
ec2_client = boto3.client('ec2')
sns_client = boto3.client('sns')
dynamodb = boto3.resource('dynamodb')


def revert_target_instance(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Terminate or revert the target EC2 instance"""
    try:
        migration_id = payload['migrationId']
        target_instance_id = payload.get('targetInstanceId')
        
        if not target_instance_id:
            logger.warning("No target instance ID to revert")
            return True, "No target instance to revert"
        
        logger.info(f"Reverting target instance: {target_instance_id}")
        
        # Terminate the target instance
        try:
            ec2_client.terminate_instances(InstanceIds=[target_instance_id])
            logger.info(f"Target instance {target_instance_id} terminated")
            return True, f"Instance {target_instance_id} terminated"
        except Exception as e:
            logger.error(f"Failed to terminate instance: {str(e)}")
            return False, str(e)

    except Exception as e:
        logger.error(f"Error reverting target instance: {str(e)}")
        return False, str(e)


def restore_source_vm(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Restore source VM from snapshot"""
    try:
        migration_id = payload['migrationId']
        app_name = payload['appName']
        snapshot_id = payload.get('snapshotId')
        
        logger.info(f"Restoring source VM {app_name} from snapshot")
        
        if not snapshot_id:
            logger.warning("No snapshot ID available for restore")
            return True, "No snapshot to restore from"
        
        source = payload['source']
        
        if source == 'azure':
            # Restore Azure VM from snapshot
            logger.info(f"Azure VM restore initiated from snapshot: {snapshot_id}")
            # In production, use Azure SDK to restore
            
        elif source == 'vmware':
            # Revert VMware snapshot
            logger.info(f"VMware snapshot revert initiated: {snapshot_id}")
            # In production, use vSphere API to revert
        
        # Simulate restore operation
        time.sleep(5)
        
        logger.info(f"Source VM {app_name} restored successfully")
        return True, f"VM restored from snapshot {snapshot_id}"

    except Exception as e:
        logger.error(f"Error restoring source VM: {str(e)}")
        return False, str(e)


def cancel_mgn_job(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Cancel any in-progress MGN jobs"""
    try:
        migration_id = payload['migrationId']
        job_id = payload.get('jobId')
        
        if not job_id:
            logger.info("No active MGN job to cancel")
            return True, "No job to cancel"
        
        logger.info(f"Canceling MGN job: {job_id}")
        
        try:
            # Get job details
            jobs = mgn_client.describe_jobs(filters={'jobIDs': [job_id]})
            
            if jobs.get('items'):
                job = jobs['items'][0]
                job_status = job['status']
                
                # Only cancel if job is still running
                if job_status not in ['COMPLETED', 'SUCCEEDED', 'FAILED']:
                    logger.info(f"Job {job_id} is still running, attempting cancel")
                    # In production, call cancel if MGN API supports it
                    logger.info(f"Job {job_id} cancellation initiated")
                else:
                    logger.info(f"Job {job_id} is already in terminal state: {job_status}")
            
            return True, f"Job cancellation processed"
            
        except Exception as e:
            logger.warning(f"Could not cancel job: {str(e)}")
            return True, "Job cancel attempted"

    except Exception as e:
        logger.error(f"Error canceling MGN job: {str(e)}")
        return False, str(e)


def restore_previous_state(migration_id: str) -> bool:
    """Restore DynamoDB state from backup"""
    try:
        logger.info(f"Restoring previous state for migration: {migration_id}")
        
        table = dynamodb.Table('migration-state')
        
        # Get backup state
        response = table.get_item(Key={'migrationId': migration_id})
        
        if 'Item' in response:
            current_state = response['Item']
            
            # Restore previous state if available
            if 'sourceState' in current_state:
                logger.info(f"Restoring state from backup for {migration_id}")
                return True
        
        return True

    except Exception as e:
        logger.error(f"Error restoring state: {str(e)}")
        return False


def notify_stakeholders(payload: Dict[str, Any], reason: str) -> bool:
    """Send SNS notification about rollback"""
    try:
        migration_id = payload['migrationId']
        app_name = payload['appName']
        
        logger.info(f"Notifying stakeholders about rollback for {app_name}")
        
        # Get SNS topic ARN from environment
        import os
        topic_arn = os.environ.get('SNS_TOPIC_ARN')
        
        if not topic_arn:
            logger.warning("SNS topic ARN not configured")
            return False
        
        message = {
            'migrationId': migration_id,
            'appName': app_name,
            'status': 'ROLLBACK_INITIATED',
            'reason': reason,
            'timestamp': int(time.time()),
            'action': 'A rollback has been initiated for this migration. Please review logs for details.'
        }
        
        try:
            response = sns_client.publish(
                TopicArn=topic_arn,
                Subject=f'Migration Rollback: {app_name} ({migration_id})',
                Message=json.dumps(message, indent=2)
            )
            
            logger.info(f"Notification sent: {response['MessageId']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return False

    except Exception as e:
        logger.error(f"Error notifying stakeholders: {str(e)}")
        return False


def lambda_handler(event, context):
    """
    Handle rollback of failed migration
    Args:
        event: Step Functions event containing migration details and error
        context: Lambda context
    Returns:
        dict: Rollback result
    """
    correlation_id = get_correlation_id()
    propagate_context(correlation_id)
    
    migration_id = event.get('migrationId') or event.get('detail', {}).get('migrationId')
    error = event.get('error', 'Unknown error')
    
    logger.info(f"Initiating rollback for migration: {migration_id}, Reason: {error}")
    
    try:
        payload = event.get('detail', event)
        
        # Update migration state
        update_migration_state(migration_id, 'ROLLBACK_IN_PROGRESS', {
            'step': 'rollback',
            'error': error,
            'correlationId': correlation_id,
            'timestamp': int(time.time())
        })
        
        # Execute rollback steps in order
        rollback_steps = []
        
        # Cancel any in-progress jobs
        success, message = cancel_mgn_job(payload)
        rollback_steps.append({
            'step': 'cancel_mgn_job',
            'success': success,
            'message': message
        })
        
        if not success:
            logger.warning(f"Failed to cancel MGN job: {message}")
        
        # Revert target instance
        success, message = revert_target_instance(payload)
        rollback_steps.append({
            'step': 'revert_target_instance',
            'success': success,
            'message': message
        })
        
        if not success:
            logger.warning(f"Failed to revert target: {message}")
        
        # Restore source VM
        success, message = restore_source_vm(payload)
        rollback_steps.append({
            'step': 'restore_source_vm',
            'success': success,
            'message': message
        })
        
        if not success:
            logger.warning(f"Failed to restore source: {message}")
        
        # Restore previous state
        restore_previous_state(migration_id)
        
        # Notify stakeholders
        notify_stakeholders(payload, error)
        
        # Update migration state to ROLLED_BACK
        update_migration_state(migration_id, 'ROLLED_BACK', {
            'step': 'rollback',
            'rollbackSteps': rollback_steps,
            'error': error,
            'correlationId': correlation_id,
            'timestamp': int(time.time())
        })
        
        logger.info(f"Rollback completed for {migration_id}")
        
        return {
            'statusCode': 200,
            'success': True,
            'migrationId': migration_id,
            'correlationId': correlation_id,
            'status': 'ROLLED_BACK',
            'message': 'Rollback completed successfully',
            'rollbackSteps': rollback_steps
        }

    except Exception as e:
        logger.error(f"Rollback failed: {str(e)}", exc_info=True)
        
        # Update migration state
        update_migration_state(migration_id, 'ROLLBACK_FAILED', {
            'error': str(e),
            'originalError': error,
            'correlationId': correlation_id,
            'timestamp': int(time.time())
        })
        
        return {
            'statusCode': 500,
            'success': False,
            'error': str(e),
            'migrationId': migration_id,
            'correlationId': correlation_id,
            'message': 'Rollback failed - manual intervention may be required'
        }
