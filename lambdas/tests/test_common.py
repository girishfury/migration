"""Tests for common utilities."""
import pytest
from common.correlation import generate_correlation_id, extract_correlation_id
from common.logger import get_logger


def test_generate_correlation_id():
    """Test correlation ID generation."""
    correlation_id = generate_correlation_id()
    
    assert correlation_id.startswith("mig-")
    assert len(correlation_id) > 4


def test_extract_correlation_id_from_detail():
    """Test extracting correlation ID from event detail."""
    event = {
        "detail": {
            "correlation_id": "mig-12345"
        }
    }
    
    correlation_id = extract_correlation_id(event)
    assert correlation_id == "mig-12345"


def test_extract_correlation_id_from_headers():
    """Test extracting correlation ID from headers."""
    event = {
        "headers": {
            "X-Correlation-ID": "mig-67890"
        }
    }
    
    correlation_id = extract_correlation_id(event)
    assert correlation_id == "mig-67890"


def test_extract_correlation_id_generate_new():
    """Test generating new correlation ID if not found."""
    event = {}
    
    correlation_id = extract_correlation_id(event)
    
    assert correlation_id.startswith("mig-")


def test_get_logger():
    """Test logger initialization."""
    logger = get_logger("test")
    
    assert logger is not None
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
    assert hasattr(logger, "warning")
