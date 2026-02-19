"""Correlation ID management for distributed tracing."""
import uuid
from typing import Optional


def generate_correlation_id() -> str:
    """Generate a unique correlation ID."""
    return f"mig-{uuid.uuid4().hex[:8]}"


def extract_correlation_id(event: dict) -> str:
    """Extract correlation ID from event or generate new one."""
    # Try to get from various sources
    if "correlation_id" in event:
        return event["correlation_id"]
    
    if "detail" in event and "correlation_id" in event.get("detail", {}):
        return event["detail"]["correlation_id"]
    
    if "headers" in event:
        correlation_id = event["headers"].get("X-Correlation-ID")
        if correlation_id:
            return correlation_id
    
    # Generate new if not found
    return generate_correlation_id()


def inject_correlation_id(event: dict, correlation_id: str) -> dict:
    """Inject correlation ID into event."""
    if "detail" not in event:
        event["detail"] = {}
    
    event["detail"]["correlation_id"] = correlation_id
    return event
