"""
Callback Handler Lambda Function

Sends migration status to callback URL, updates external systems.
"""
import os
import json
from typing import Dict, Any

import requests

from common.logger import get_logger
from common.correlation import extract_correlation_id
from common.errors import MigrationError

logger = get_logger(__name__)


def send_callback(
    callback_url: str,
    payload: Dict[str, Any],
    timeout: int = 30,
) -> Dict[str, Any]:
    """Send callback to external system."""
    logger.info("Sending callback", extra={"url": callback_url})
    
    try:
        response = requests.post(
            callback_url,
            json=payload,
            timeout=timeout,
            headers={
                "Content-Type": "application/json",
                "X-Migration-Callback": "true",
            },
        )
        
        response.raise_for_status()
        
        logger.info(
            "Callback sent successfully",
            extra={
                "status_code": response.status_code,
                "url": callback_url,
            },
        )
        
        return {
            "status": "SUCCESS",
            "statusCode": response.status_code,
            "responseTime": response.elapsed.total_seconds(),
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(
            "Callback request failed",
            extra={
                "error": str(e),
                "url": callback_url,
            },
        )
        raise MigrationError(
            f"Callback request failed: {str(e)}",
            "CALLBACK_ERROR",
            details={"url": callback_url},
        )


def format_callback_payload(event: Dict[str, Any]) -> Dict[str, Any]:
    """Format event for callback."""
    detail = event.get("detail", {})
    
    callback_payload = {
        "migrationId": detail.get("migrationId"),
        "status": detail.get("status"),
        "appName": detail.get("appName"),
        "environment": detail.get("environment"),
        "wave": detail.get("wave"),
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "correlationId": extract_correlation_id(event),
    }
    
    # Include error details if failure
    if "errorCode" in detail:
        callback_payload["error"] = {
            "code": detail.get("errorCode"),
            "message": detail.get("errorMessage"),
        }
    
    # Include success details
    if detail.get("status") == "SUCCESS":
        callback_payload["successDetails"] = {
            "completedAt": detail.get("completedAt"),
            "targetVmName": detail.get("targetVmName"),
        }
    
    return callback_payload


def lambda_handler(event, context):
    """
    Handle migration status callbacks.
    
    Args:
        event: EventBridge event
        context: Lambda context
    
    Returns:
        dict: Callback result
    """
    try:
        detail = event.get("detail", {})
        correlation_id = extract_correlation_id(event)
        logger.set_correlation_id(correlation_id)
        
        migration_id = detail.get("migrationId")
        callback_url = detail.get("callbackUrl")
        
        logger.info(
            "Processing callback",
            extra={
                "migrationId": migration_id,
                "callbackUrl": callback_url,
            },
        )
        
        # Check if callback URL is provided
        if not callback_url:
            logger.warning(
                "No callback URL provided",
                extra={"migrationId": migration_id},
            )
            return {
                "statusCode": 200,
                "body": {
                    "migrationId": migration_id,
                    "status": "SKIPPED",
                    "reason": "No callback URL",
                },
            }
        
        # Format payload for callback
        callback_payload = format_callback_payload(event)
        
        # Send callback
        callback_result = send_callback(callback_url, callback_payload)
        
        logger.info(
            "Callback processing completed",
            extra={
                "migrationId": migration_id,
                "callbackResult": callback_result,
            },
        )
        
        return {
            "statusCode": 200,
            "body": {
                "migrationId": migration_id,
                "status": "CALLBACK_SENT",
                "details": callback_result,
            },
        }
        
    except MigrationError as e:
        logger.error("Callback processing failed", extra=e.to_dict())
        
        # Return error but don't fail the workflow
        return {
            "statusCode": 200,
            "body": {
                "migrationId": detail.get("migrationId", "unknown"),
                "status": "CALLBACK_FAILED",
                "error": e.to_dict(),
            },
        }
        
    except Exception as e:
        logger.error("Unexpected error in callback handler", extra={"error": str(e)})
        return {
            "statusCode": 200,
            "body": {
                "migrationId": detail.get("migrationId", "unknown"),
                "status": "CALLBACK_FAILED",
                "error": str(e),
            },
        }
