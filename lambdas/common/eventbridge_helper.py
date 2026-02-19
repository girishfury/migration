"""EventBridge helper utilities for event publishing."""
import boto3
import json
from typing import Dict, Any, Optional


class EventBridgePublisher:
    """Publishes events to EventBridge custom bus."""

    def __init__(self, bus_name: str, region: str = "us-east-1"):
        """Initialize EventBridge client."""
        self.client = boto3.client("events", region_name=region)
        self.bus_name = bus_name

    def publish_event(
        self,
        detail_type: str,
        detail: Dict[str, Any],
        source: str = "migration.orchestration",
        resources: Optional[list] = None,
    ) -> str:
        """Publish event to EventBridge."""
        response = self.client.put_events(
            Entries=[
                {
                    "EventBusName": self.bus_name,
                    "Source": source,
                    "DetailType": detail_type,
                    "Detail": json.dumps(detail),
                    "Resources": resources or [],
                }
            ]
        )
        
        if response.get("FailedEntryCount", 0) > 0:
            raise Exception(
                f"Failed to publish event: {response.get('Entries', [])}"
            )
        
        return response["Entries"][0]["EventId"]

    def publish_success_event(
        self,
        migration_id: str,
        correlation_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish migration success event."""
        event_detail = {
            "migrationId": migration_id,
            "correlationId": correlation_id,
            "status": "SUCCESS",
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }
        
        if details:
            event_detail.update(details)
        
        return self.publish_event(
            detail_type="MigrationSucceeded",
            detail=event_detail,
        )

    def publish_failure_event(
        self,
        migration_id: str,
        correlation_id: str,
        error_code: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish migration failure event."""
        event_detail = {
            "migrationId": migration_id,
            "correlationId": correlation_id,
            "status": "FAILED",
            "errorCode": error_code,
            "errorMessage": error_message,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }
        
        if details:
            event_detail.update(details)
        
        return self.publish_event(
            detail_type="MigrationFailed",
            detail=event_detail,
        )

    def publish_status_event(
        self,
        migration_id: str,
        correlation_id: str,
        current_step: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Publish migration status event."""
        event_detail = {
            "migrationId": migration_id,
            "correlationId": correlation_id,
            "currentStep": current_step,
            "status": status,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }
        
        if details:
            event_detail.update(details)
        
        return self.publish_event(
            detail_type="MigrationStatusUpdated",
            detail=event_detail,
        )
