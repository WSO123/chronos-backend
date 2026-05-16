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
