"""Alerting domain exceptions."""


class AlertingError(Exception):
    """Base exception for alerting failures."""


class AlertDeliveryError(AlertingError):
    """Raised when external alert delivery fails."""
