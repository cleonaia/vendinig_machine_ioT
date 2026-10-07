class DomainError(Exception):
    def __init__(self, message: str, code: str = "domain_error", status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message
