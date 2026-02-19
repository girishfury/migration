"""
Callback Handler Lambda Function
Sends migration status to callback URL, updates external systems
"""

import json
import logging
import boto3
import requests
from typing import Dict, Any, Tuple
from datetime import datetime

from common.logger import get_logger
from common.correlation import get_correlation_id, propagate_context

logger = get_logger(__name__)
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')


def get_auth_header(callback_url: str) -> Dict[str, str]:
    """Get authentication header if required for callback"""
    try:
        # Check if auth is required
        if '/api/' not in callback_url:
            return {}
        
        # Try to get auth token from Secrets Manager
        try:
            secret = secrets_client.get_secret_value(
                SecretId='migration/callback-auth'
            )
            auth_token = json.loads(secret['SecretString']).get('token')
            
            if auth_token:
                return {'Authorization': f'Bearer {auth_token}'}
        except secrets_client.exceptions.ResourceNotFoundException:
            logger.warning("No auth secret found for callback")
        
        return {}

    except Exception as e:
        logger.error(f"Error getting auth header: {str(e)}")
        return {}


def send_callback(callback_url: str, status_payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Send migration status to callback URL"""
    try:
        if not callback_url:
            logger.warning("No callback URL provided")
            return True, "No callback URL"
        
        logger.info(f"Sending callback to: {callback_url}")
        
        headers = {
            'Content-Type': 'application/json',
            'X-Migration-Source': 'AWS-MGN-Orchestrator'
        }
        
        # Add auth if available
        auth_headers = get_auth_header(callback_url)
        headers.update(auth_headers)
        
        # Add correlation ID
        headers['X-Correlation-ID'] = status_payload.get('correlationId', '')
        
        # Set timeout for request
        response = requests.post(
            callback_url,
            json=status_payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code not in [200, 201, 202]:
            return False, f"Callback failed with status {response.status_code}: {response.text}"
        
        logger.info(f"Callback sent successfully. Response: {response.status_code}")
        return True, "Callback sent successfully"

    except requests.RequestException as e:
        logger.error(f"Request error sending callback: {str(e)}")
        return False, str(e)
    
    except Exception as e:
        logger.error(f"Error sending callback: {str(e)}")
        return False, str(e)


def update_cmdb(migration_id: str, status_payload: Dict[str, Any]) -> bool:
    """Update CMDB with migration status"""
    try:
        logger.info(f"Updating CMDB for migration: {migration_id}")
        
        # Store in DynamoDB for CMDB integration
        table = dynamodb.Table('migration-state')
        
        cmdb_update = {
            'timestamp': datetime.utcnow().isoformat(),
            'migrationId': migration_id,
            'status': status_payload.get('status'),
            'appName': status_payload.get('appName'),
            'targetInstanceId': status_payload.get('targetInstanceId'),
            'targetIpAddress': status_payload.get('targetIpAddress')
        }
        
        table.update_item(
            Key={'migrationId': migration_id},
            UpdateExpression='SET cmdbUpdate = :update',
            ExpressionAttributeValues={':update': json.dumps(cmdb_update)}
        )
        
        logger.info(f"CMDB updated for {migration_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to update CMDB: {str(e)}")
        return False


def format_callback_payload(event: Dict[str, Any]) -> Dict[str, Any]:
    """Format the callback payload with migration status"""
    migration_id = event.get('migrationId') or event.get('detail', {}).get('migrationId')
    payload = event.get('detail', event)
    
    callback_payload = {
        'migrationId': migration_id,
        'appName': payload.get('appName'),
        'status': event.get('status', 'IN_PROGRESS'),
        'launchType': event.get('launchType'),
        'jobId': event.get('jobId'),
        'timestamp': int(datetime.utcnow().timestamp() * 1000),
        'correlationId': event.get('correlationId'),
        'jobStatus': event.get('jobStatus'),
        'targetInstanceId': event.get('targetInstanceId'),
        'targetIpAddress': event.get('targetIpAddress'),
        'replicationLag': event.get('replicationLag'),
        'healthStatus': event.get('healthStatus'),
        'error': event.get('error'),
        'sourceEnvironment': payload.get('source'),
        'targetEnvironment': payload.get('target'),
        'wave': payload.get('wave'),
        'environment': payload.get('environment')
    }
    
    return callback_payload


def lambda_handler(event, context):
    """
    Send migration status callback to external systems
    Args:
        event: Step Functions event containing migration payload and status
        context: Lambda context
    Returns:
        dict: Callback result
    """
    correlation_id = get_correlation_id()
    propagate_context(correlation_id)
    
    migration_id = event.get('migrationId') or event.get('detail', {}).get('migrationId')
    logger.info(f"Processing callback for migration: {migration_id}")
    
    try:
        payload = event.get('detail', event)
        callback_url = payload.get('callbackUrl')
        
        # Format callback payload
        callback_payload = format_callback_payload(event)
        callback_payload['correlationId'] = correlation_id
        
        logger.info(f"Callback payload: {json.dumps(callback_payload)}")
        
        # Send callback to external system
        success, message = send_callback(callback_url, callback_payload)
        
        if not success:
            logger.warning(f"Callback delivery failed: {message}")
            # Don't fail the migration if callback fails, just log it
        
        # Update CMDB
        cmdb_success = update_cmdb(migration_id, callback_payload)
        
        if not cmdb_success:
            logger.warning(f"CMDB update failed for {migration_id}")
        
        return {
            'statusCode': 200,
            'success': True,
            'migrationId': migration_id,
            'correlationId': correlation_id,
            'callbackSent': success,
            'callbackMessage': message,
            'cmdbUpdated': cmdb_success
        }

    except Exception as e:
        logger.error(f"Callback processing failed: {str(e)}", exc_info=True)
        
        return {
            'statusCode': 500,
            'success': False,
            'error': str(e),
            'migrationId': migration_id,
            'correlationId': correlation_id
        }
