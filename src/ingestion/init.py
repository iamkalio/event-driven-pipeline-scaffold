"""Ingestion domain exceptions."""


class IngestionError(Exception):
    """Base exception for ingestion failures."""


class PublishError(IngestionError):
    """Raised when Kafka publishing fails after retries."""


class SourceValidationError(IngestionError):
    """Raised when a source payload cannot be normalized."""
