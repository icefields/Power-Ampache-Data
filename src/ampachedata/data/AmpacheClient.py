"""Public facade. Owns the write-through flow for every read method:

    fetch (Transport) -> map (mappers) -> upsert (repositories) -> read back (repositories)

Repositories are SQL-only and never see HTTP; mappers never see SQL or domain."""
from ..domain.PingResult import PingResult
from .ApiMethod import ApiMethod
from .Transport import UrllibTransport
from .auth.SessionManager import ENDPOINT_PATH, SessionManager
from .db.Database import Database
from .db.mappers.SessionMapper import mapSession
from .db.repositories.CredentialsRepository import CredentialsRepository
from .db.repositories.SessionRepository import SessionRepository
from .errors import AmpacheError, InvalidHandshakeError, raiseForError


class AmpacheClient:
    def __init__(self, dbPath: str, transport=None):
        database = Database(dbPath)
        self._transport = transport if transport is not None else UrllibTransport()
        self._credentialsRepository = CredentialsRepository(database)
        self._sessionRepository = SessionRepository(database)
        self._sessionManager = SessionManager(
            self._transport, self._sessionRepository, self._credentialsRepository
        )

    def ping(self) -> PingResult:
        """Health check / expiry probe.

        With a session token: extends the session; fresh auth/expiry are persisted
        to SessionEntity BEFORE returning (write-through). Without one: anonymous
        probe returning server/version/compatible only."""
        credentials = self._credentialsRepository.getCredentials()
        if credentials is None:
            raise AmpacheError("no credentials stored in CredentialsEntity; serverUrl unknown")
        session = self._sessionRepository.getSession()
        if session is None or not session.auth:
            payload = self._send(ApiMethod.PING, {}, token=None, serverUrl=credentials.serverUrl)
            raiseForError(payload)
            return PingResult(
                authenticated=False,
                api=payload.get("api") or "",
                server=payload.get("server") or "",
                version=payload.get("version") or "",
                compatible=payload.get("compatible") or "",
            )
        payload = self._sendWithAuth(ApiMethod.PING, {})
        if payload.get("auth") or payload.get("session_expire"):
            self._sessionRepository.upsertSession(mapSession(payload))
        session = self._sessionRepository.getSession()
        return PingResult(
            authenticated=True, auth=session.auth, sessionExpire=session.sessionExpire, api=session.api
        )

    def _sendWithAuth(self, action, params):
        credentials = self._credentialsRepository.getCredentials()
        token = self._sessionManager.ensureSession()
        payload = self._send(action, params, token, credentials.serverUrl)
        try:
            raiseForError(payload)
        except InvalidHandshakeError:
            # 4701: silent re-auth from stored credentials, retry ONCE. goodbye is never called.
            token = self._sessionManager.reauthenticate()
            payload = self._send(action, params, token, credentials.serverUrl)
            raiseForError(payload)
        return payload

    def _send(self, action, params, token, serverUrl):
        url = serverUrl.rstrip("/") + ENDPOINT_PATH
        requestParams = {"action": action.value}
        requestParams.update(params)
        headers = {}
        if token:
            # Session token via Bearer header — NEVER the query string.
            headers["Authorization"] = "Bearer " + token
        return self._transport.send("GET", url, requestParams, headers)
