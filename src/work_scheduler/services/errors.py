class ServiceError(Exception):
    """Base for failures that are shown to the user as a readable message."""


class ValidationError(ServiceError):
    """The data entered by the user is incomplete or malformed."""


class ConflictError(ServiceError):
    """The operation is refused because other records depend on this one."""
