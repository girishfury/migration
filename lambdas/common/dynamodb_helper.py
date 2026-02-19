"""DynamoDB helper utilities for migration state tracking."""
import boto3
from typing import Dict, Any, Optional, List
from datetime import datetime


class MigrationStateManager:
    """Manages migration state in DynamoDB."""

    def __init__(self, table_name: str, region: str = "us-east-1"):
        """Initialize DynamoDB client and table."""
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)

    def save_migration_state(
        self,
        migration_id: str,
        state: Dict[str, Any],
    ) -> None:
        """Save migration state to DynamoDB."""
        item = {
            "migrationId": migration_id,
            "status": state.get("status", "PENDING"),
            "wave": state.get("wave"),
            "appName": state.get("appName"),
            "source": state.get("source"),
            "target": state.get("target"),
            "environment": state.get("environment"),
            "updatedAt": datetime.utcnow().isoformat(),
            "executionDetails": state.get("executionDetails", {}),
            "correlationId": state.get("correlationId"),
        }
        
        self.table.put_item(Item=item)

    def get_migration_state(self, migration_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve migration state from DynamoDB."""
        response = self.table.get_item(Key={"migrationId": migration_id})
        return response.get("Item")

    def update_migration_status(
        self,
        migration_id: str,
        status: str,
        execution_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update migration status."""
        update_expression = "SET #status = :status, updatedAt = :updated_at"
        expression_values = {
            ":status": status,
            ":updated_at": datetime.utcnow().isoformat(),
        }
        
        if execution_details:
            update_expression += ", executionDetails = :details"
            expression_values[":details"] = execution_details
        
        self.table.update_item(
            Key={"migrationId": migration_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues=expression_values,
        )

    def query_by_wave(self, wave: str) -> List[Dict[str, Any]]:
        """Query migrations by wave."""
        response = self.table.query(
            IndexName="waveIndex",
            KeyConditionExpression="wave = :wave",
            ExpressionAttributeValues={":wave": wave},
        )
        return response.get("Items", [])

    def query_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Query migrations by status."""
        response = self.table.scan(
            FilterExpression="#status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": status},
        )
        return response.get("Items", [])

    def query_by_app_and_status(
        self, app_name: str, status: str
    ) -> List[Dict[str, Any]]:
        """Query migrations by app name and status."""
        response = self.table.scan(
            FilterExpression="appName = :app AND #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":app": app_name,
                ":status": status,
            },
        )
        return response.get("Items", [])
