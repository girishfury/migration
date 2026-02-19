"""Structured logging utility with correlation ID support."""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional


class CorrelatedLogger:
    """Logger with correlation ID support for distributed tracing."""

    def __init__(self, name: str):
        """Initialize logger with name."""
        self.logger = logging.getLogger(name)
        self.correlation_id: Optional[str] = None
        
        # Setup structured logging
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set correlation ID for request tracing."""
        self.correlation_id = correlation_id

    def _log(self, level: str, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Internal log method with correlation ID."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "correlation_id": self.correlation_id,
        }
        
        if extra:
            log_entry.update(extra)
        
        log_method = getattr(self.logger, level.lower())
        log_method(json.dumps(log_entry))

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log info level message."""
        self._log("INFO", message, extra)

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log error level message."""
        self._log("ERROR", message, extra)

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log warning level message."""
        self._log("WARNING", message, extra)

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log debug level message."""
        self._log("DEBUG", message, extra)


def get_logger(name: str) -> CorrelatedLogger:
    """Get a correlated logger instance."""
    return CorrelatedLogger(name)
