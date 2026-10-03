class SignatureManagerError(Exception):
    """Base class for errors raised by this package."""


class AuthenticationError(SignatureManagerError):
    """Could not get an access token from Entra ID."""


class GraphError(SignatureManagerError):
    """Microsoft Graph returned an error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ExchangeError(SignatureManagerError):
    """Exchange Online PowerShell failed."""
