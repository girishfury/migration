"""Tests for validate input handler."""
import pytest
from unittest.mock import patch, MagicMock

from validate_input import lambda_handler, validate_payload_content
from common.errors import ValidationError, PrerequisiteError


def test_validate_payload_content_valid():
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
    validate_payload_content(payload)


def test_validate_payload_content_missing_field():
    """Test validation fails for missing field."""
    payload = {
        "appName": "billing-app",
        # Missing required fields
    }
    
    with pytest.raises(ValidationError):
        validate_payload_content(payload)


@patch("validate_input.state_manager")
@patch("validate_input.eventbridge")
def test_validate_input_handler_success(mock_eventbridge, mock_state_manager):
    """Test successful input validation."""
    mock_eventbridge.publish_status_event.return_value = "event-123"
    
    event = {
        "detail": {
            "migrationId": "mig-12345",
            "appName": "billing-app",
            "source": "azure",
            "target": "aws",
            "environment": "prod",
            "wave": "wave-3",
        }
    }
    
    result = lambda_handler(event, None)
    
    assert result["statusCode"] == 200
    assert result["body"]["status"] == "VALIDATED"
    mock_state_manager.save_migration_state.assert_called_once()
