"""Owns the session lifecycle: when to handshake, silent re-auth on expiry/4701.

goodbye/logout is NEVER called — tokens are time-limited and simply replaced."""
import time
from datetime import datetime, timezone

from ..ApiMethod import ApiMethod
from ..ErrorCode import ErrorCode
from ..db.mappers.SessionMapper import mapSession
from ..errors import InvalidHandshakeError, raiseForError
from .Handshake import buildPassphrase

DEFAULT_API_VERSION = "8.0.0"
ENDPOINT_PATH = "/server/json.server.php"


class SessionManager:
    def __init__(self, transport, sessionRepository, credentialsRepository):
        self._transport = transport
        self._sessionRepository = sessionRepository
        self._credentialsRepository = credentialsRepository

    def ensureSession(self) -> str:
        """Return a valid session token, handshaking first if none exists or it expired."""
        session = self._sessionRepository.getSession()
        if session is not None and session.auth and not isExpired(session.sessionExpire):
            return session.auth
        return self._handshake()

    def reauthenticate(self) -> str:
        """Silent re-auth after a 4701. Never logs out first."""
        return self._handshake()

    def _handshake(self) -> str:
        credentials = self._credentialsRepository.getCredentials()
        if credentials is None:
            raise InvalidHandshakeError(
                "no credentials stored in CredentialsEntity", ErrorCode.INVALID_HANDSHAKE
            )
        timestamp = str(int(time.time()))
        passphrase = buildPassphrase(timestamp, credentials.passwordHash)
        # Handshake is the ONE call where auth travels as a request parameter — no
        # session token exists yet. Every later call uses Authorization: Bearer.
        params = {
            "action": ApiMethod.HANDSHAKE.value,
            "timestamp": timestamp,
            "user": credentials.username,
            "auth": passphrase,
            "version": DEFAULT_API_VERSION,
        }
        url = credentials.serverUrl.rstrip("/") + ENDPOINT_PATH
        payload = self._transport.send("GET", url, params, {})
        raiseForError(payload)
        self._sessionRepository.upsertSession(mapSession(payload))
        session = self._sessionRepository.getSession()  # write-through: read back from DB
        if session is None or not session.auth:
            raise InvalidHandshakeError(
                "handshake response carried no session token", ErrorCode.INVALID_HANDSHAKE
            )
        return session.auth


def isExpired(sessionExpire: str) -> bool:
    """ISO 8601 expiry vs now (UTC). Unparseable => treat as expired."""
    try:
        expires = datetime.fromisoformat(sessionExpire)
    except (TypeError, ValueError):
        return True
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires <= datetime.now(timezone.utc)
