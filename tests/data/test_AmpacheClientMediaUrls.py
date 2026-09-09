"""Pure URL-construction tests for getStreamUrl/getDownloadUrl.

No fake transport, no DB: the client is built via __new__ with stub
repositories — URL building touches only CredentialsRepository (serverUrl)
and SessionManager (live token). transport=None proves no network call
happens (any send would raise AttributeError)."""
from urllib.parse import parse_qsl, urlsplit

import pytest

from ampachedata import AmpacheClient, Credentials, InvalidHandshakeError
from ampachedata.data.auth.SessionManager import SessionManager

SERVER_URL = "https://demo.ampache.dev"
ENDPOINT = "/server/json.server.php"
TOKEN_A = "aaaabbbbccccdddd0000111122223333"
TOKEN_B = "bbbbccccddddeeee1111222233330000"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"


class _FakeSession:
    """Duck-type of domain.Session — ensureSession reads only auth/sessionExpire."""

    def __init__(self, auth):
        self.auth = auth
        self.sessionExpire = FAR_FUTURE


class _FakeSessionRepository:
    def __init__(self, session):
        self._session = session

    def getSession(self):
        return self._session


class _FakeCredentialsRepository:
    def getCredentials(self):
        return Credentials(
            username="user", passwordHash="x" * 64, authToken="", serverUrl=SERVER_URL
        )


def _makeClient(session):
    credentialsRepository = _FakeCredentialsRepository()
    sessionManager = SessionManager(None, _FakeSessionRepository(session), credentialsRepository)
    client = AmpacheClient.__new__(AmpacheClient)  # bypass __init__: no Database, no transport
    client._credentialsRepository = credentialsRepository
    client._sessionManager = sessionManager
    return client


def _params(url):
    parts = urlsplit(url)
    assert parts.scheme == "https"
    assert parts.netloc == "demo.ampache.dev"
    assert parts.path == ENDPOINT
    return dict(parse_qsl(parts.query))


def testStreamUrlExactParams():
    client = _makeClient(_FakeSession(TOKEN_A))
    params = _params(client.getStreamUrl("132"))
    assert params == {"action": "stream", "auth": TOKEN_A, "filter": "132", "type": "song"}


def testStreamUrlAppendsOptionalParamsOnlyWhenSet():
    client = _makeClient(_FakeSession(TOKEN_A))
    params = _params(client.getStreamUrl("132", format="raw", bitrate=192000, offset=60, stats=0))
    assert params == {
        "action": "stream", "auth": TOKEN_A, "filter": "132", "type": "song",
        "format": "raw", "bitrate": "192000", "offset": "60", "stats": "0",
        # stats=0 proves falsy-but-not-None values ARE appended
    }


def testDownloadUrlExactParams():
    client = _makeClient(_FakeSession(TOKEN_A))
    params = _params(client.getDownloadUrl("132"))
    assert params == {"action": "download", "auth": TOKEN_A, "filter": "132", "type": "song"}


def testDownloadUrlAppendsOptionalParamsOnlyWhenSet():
    client = _makeClient(_FakeSession(TOKEN_A))
    params = _params(client.getDownloadUrl("132", format="mp3", bitrate=192000, stats=1))
    assert params == {
        "action": "download", "auth": TOKEN_A, "filter": "132", "type": "song",
        "format": "mp3", "bitrate": "192000", "stats": "1",
    }


def testTokenIsReadLivePerRequestNeverCached():
    session = _FakeSession(TOKEN_A)
    client = _makeClient(session)
    first = _params(client.getStreamUrl("132"))
    session.auth = TOKEN_B  # token rotated by a silent re-auth
    second = _params(client.getStreamUrl("132"))
    assert first["auth"] == TOKEN_A
    assert second["auth"] == TOKEN_B


def testTerminatedSessionRaises():
    client = _makeClient(_FakeSession(TOKEN_A))
    client._sessionManager.terminate()  # exactly what goodbye() does on success
    with pytest.raises(InvalidHandshakeError):
        client.getStreamUrl("132")
    with pytest.raises(InvalidHandshakeError):
        client.getDownloadUrl("132")
