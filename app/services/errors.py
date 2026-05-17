class DomainError(Exception):
    status_code = 400
    code = "DOMAIN_ERROR"

    def __init__(self, message: str | None = None):
        self.message = message or self.code
        super().__init__(self.message)


class NotFoundError(DomainError):
    status_code = 404
    code = "NOT_FOUND"


class InvalidStateError(DomainError):
    status_code = 400
    code = "INVALID_STATE"


class ValidationDomainError(DomainError):
    status_code = 400
    code = "VALIDATION_ERROR"


class AuthenticationError(DomainError):
    status_code = 401
    code = "AUTHENTICATION_FAILED"


class ForbiddenError(DomainError):
    status_code = 403
    code = "FORBIDDEN"


class ConflictError(DomainError):
    status_code = 409
    code = "CONFLICT"


class SecurityConfigurationError(DomainError):
    status_code = 500
    code = "INSECURE_AUTH_CONFIGURATION"
