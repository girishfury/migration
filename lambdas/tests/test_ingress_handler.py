"""Tests for ingress handler."""
import json
import pytest
from unittest.mock import patch, MagicMock

from ingress_handler import lambda_handler, validate_message
from common.errors import ValidationError


def test_validate_message_valid_payload():
    """Test validation of valid payload."""
    payload = {
        "migrationId": "mig-12345",
        "appName": "billing-app",
        "source": "azure",
        "target": "aws",
        "environment": "prod",
        "wave": "wave-3",
    }
    
    # Should not raise
    validate_message(payload)


def test_validate_message_missing_required_field():
    """Test validation fails for missing required field."""
    payload = {
        "appName": "billing-app",
        "source": "azure",
        "target": "aws",
        "environment": "prod",
        "wave": "wave-3",
    }
    
    with pytest.raises(ValidationError):
        validate_message(payload)


@patch("ingress_handler.eventbridge")
def test_ingress_handler_successful(mock_eventbridge):
    """Test successful message ingestion."""
    mock_eventbridge.publish_event.return_value = "event-123"
    
    event = {
        "Records": [
            {
                "messageId": "msg-123",
                "body": json.dumps({
                    "migrationId": "mig-12345",
                    "appName": "billing-app",
                    "source": "azure",
                    "target": "aws",
                    "environment": "prod",
                    "wave": "wave-3",
                }),
            }
        ]
    }
    
    result = lambda_handler(event, None)
    
    assert result["statusCode"] == 200
    assert len(json.loads(result["body"])["successful"]) == 1


@patch("ingress_handler.eventbridge")
def test_ingress_handler_invalid_message(mock_eventbridge):
    """Test handling of invalid message."""
    event = {
        "Records": [
            {
                "messageId": "msg-123",
                "body": json.dumps({
                    "appName": "billing-app",
                    # Missing required fields
                }),
            }
        ]
    }
    
    result = lambda_handler(event, None)
    
    assert result["statusCode"] == 200
    assert len(json.loads(result["body"])["failed"]) == 1
