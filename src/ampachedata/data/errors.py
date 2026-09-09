"""Typed exception hierarchy. Raw HTTP status codes never escape data/."""
from .ErrorCode import ErrorCode


class AmpacheError(Exception):
    """Base class for every error raised by ampachedata."""


class DatabaseError(AmpacheError):
    """musicdb.db missing or unusable. The library never creates or alters schema."""


class CredentialValidationError(AmpacheError):
    """Bootstrap input failed validation. Messages are static text — they never
    contain the cleartext password or the stored hash."""


class CacheVerificationError(AmpacheError):
    """Post-write read-back mismatch: after flag()/rate() the re-fetched
    entity's flag/rating does not match the value just set — the server's
    success envelope and its returned object disagree."""


class ApiError(AmpacheError):
    """An Ampache error envelope: {'error': {'code': ..., 'message': ...}}."""

    def __init__(self, message, code):
        self.message = message
        self.code = int(code)
        super().__init__("[{}] {}".format(self.code, message))


class InvalidHandshakeError(ApiError):
    """4701 (or HTTP 401/403) — token expired/invalid or bad credentials.
    Triggers silent re-auth + exactly one retry."""


class AccessDeniedError(ApiError):
    """4703."""


class NotFoundError(ApiError):
    """4704."""


class DeprecatedError(ApiError):
    """4706."""


class BadRequestError(ApiError):
    """4710."""


class UnknownApiError(ApiError):
    """Any code not in the spec."""


_ERROR_CODE_MAP = {
    ErrorCode.INVALID_HANDSHAKE: InvalidHandshakeError,
    ErrorCode.UNAUTHORIZED: InvalidHandshakeError,  # HTTP 401 on a failed handshake
    ErrorCode.FORBIDDEN: InvalidHandshakeError,  # HTTP 403 on a stale session token
    ErrorCode.ACCESS_DENIED: AccessDeniedError,
    ErrorCode.NOT_FOUND: NotFoundError,
    ErrorCode.DEPRECATED: DeprecatedError,
    ErrorCode.BAD_REQUEST: BadRequestError,
}


def raiseForError(payload):
    """Raise the typed ApiError for an error envelope; no-op on success payloads."""
    error = payload.get("error")
    if error is None:
        return
    if isinstance(error, dict):
        rawCode = error.get("code", 0)
        message = error.get("message") or ""
    else:
        rawCode = 0
        message = str(error)
    try:
        code = int(rawCode)
    except (TypeError, ValueError):
        code = 0
    raise _ERROR_CODE_MAP.get(code, UnknownApiError)(message, code)
