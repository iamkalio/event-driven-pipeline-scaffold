"""Storage domain exceptions."""


class StorageError(Exception):
    """Base exception for persistence failures."""


class RepositoryError(StorageError):
    """Raised when a repository operation fails."""
