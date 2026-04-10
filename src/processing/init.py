"""Processing domain exceptions."""


class ProcessingError(Exception):
    """Base exception for processing failures."""


class IdempotencyError(ProcessingError):
    """Raised when idempotency state cannot be read or written."""


class JoinerError(ProcessingError):
    """Raised when event joining fails."""
