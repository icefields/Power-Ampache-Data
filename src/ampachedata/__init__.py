"""ampachedata — public API. Anything not re-exported here is private."""
from .data.AmpacheClient import AmpacheClient
from .data.Bootstrap import storeCredentialsFromKey, storeCredentialsFromPassword
from .data.errors import (
    AccessDeniedError,
    AmpacheError,
    ApiError,
    BadRequestError,
    CredentialValidationError,
    DatabaseError,
    DeprecatedError,
    InvalidHandshakeError,
    NotFoundError,
    UnknownApiError,
)
from .domain.Credentials import Credentials
from .domain.PingResult import PingResult
from .domain.Session import Session

__all__ = [
    "AmpacheClient",
    "Session",
    "Credentials",
    "PingResult",
    "storeCredentialsFromPassword",
    "storeCredentialsFromKey",
    "AmpacheError",
    "ApiError",
    "DatabaseError",
    "InvalidHandshakeError",
    "AccessDeniedError",
    "NotFoundError",
    "DeprecatedError",
    "BadRequestError",
    "CredentialValidationError",
    "UnknownApiError",
]
