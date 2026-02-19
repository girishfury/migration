"""Custom exception types for migration orchestration."""


class MigrationError(Exception):
    """Base exception for migration-related errors."""

    def __init__(self, message: str, error_code: str, details: dict = None):
        """Initialize migration error."""
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert error to dictionary representation."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(MigrationError):
    """Raised when payload validation fails."""

    def __init__(self, message: str, details: dict = None):
        """Initialize validation error."""
        super().__init__(message, "VALIDATION_ERROR", details)


class PrerequisiteError(MigrationError):
    """Raised when prerequisites are not met."""

    def __init__(self, message: str, details: dict = None):
        """Initialize prerequisite error."""
        super().__init__(message, "PREREQUISITE_ERROR", details)


class SourcePreparationError(MigrationError):
    """Raised when source preparation fails."""

    def __init__(self, message: str, details: dict = None):
        """Initialize source preparation error."""
        super().__init__(message, "SOURCE_PREPARATION_ERROR", details)


class MigrationExecutionError(MigrationError):
    """Raised when migration execution fails."""

    def __init__(self, message: str, details: dict = None):
        """Initialize migration execution error."""
        super().__init__(message, "MIGRATION_EXECUTION_ERROR", details)


class VerificationError(MigrationError):
    """Raised when verification fails."""

    def __init__(self, message: str, details: dict = None):
        """Initialize verification error."""
        super().__init__(message, "VERIFICATION_ERROR", details)


class CutoverError(MigrationError):
    """Raised when cutover fails."""

    def __init__(self, message: str, details: dict = None):
        """Initialize cutover error."""
        super().__init__(message, "CUTOVER_ERROR", details)


class RollbackError(MigrationError):
    """Raised when rollback fails."""

    def __init__(self, message: str, details: dict = None):
        """Initialize rollback error."""
        super().__init__(message, "ROLLBACK_ERROR", details)
