class ServiceError(Exception):
    """Base exception for application service failures."""


class EntityNotFoundError(ServiceError):
    """Raised when a required entity does not exist."""


class ConflictError(ServiceError):
    """Raised when an operation conflicts with current data."""


class InvalidStateError(ServiceError):
    """Raised when an entity is in an invalid business state."""
