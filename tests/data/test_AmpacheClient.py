"""ping + re-auth flows through the fake transport. No network."""
import pytest

from ampachedata import NotFoundError
from ampachedata.data.db.Database import Database
from ampachedata.data.db.repositories.SessionRepository import SessionRepository

HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"

ANONYMOUS_PING = {"server": "Ampache", "version": "8.0.0", "compatible": "1", "api": "8.0.0"}
ERROR_4701 = {"error": {"code": 4701, "message": "Invalid handshake"}}
ERROR_4704 = {"error": {"code": 4704, "message": "Not found"}}


def pingOk(handshakePayload):
    return {
        "auth": handshakePayload["auth"],
        "session_expire": handshakePayload["session_expire"],
        "api": handshakePayload["api"],
    }


def testPingWithoutSessionIsAnonymous(makeClient, seedCredentials):
    seedCredentials()
    client, transport = makeClient([ANONYMOUS_PING])
    result = client.ping()
    assert result.authenticated is False
    assert result.server == "Ampache"
    assert result.version == "8.0.0"
    (request,) = transport.requests
    assert request["params"]["action"] == "ping"
    assert "Authorization" not in request["headers"]
    assert "auth" not in request["params"]


def testPingWithSessionExtendsAndPersists(dbPath, makeClient, seedCredentials, seedSession, handshakePayload):
    seedCredentials()
    seedSession(auth="oldtoken")
    client, transport = makeClient([handshakePayload])
    result = client.ping()
    assert result.authenticated is True
    assert result.auth == HANDSHAKE_AUTH
    (request,) = transport.requests
    assert request["headers"]["Authorization"] == "Bearer oldtoken"
    assert "auth" not in request["params"]  # session token never in the query string
    session = SessionRepository(Database(dbPath)).getSession()
    assert session.auth == HANDSHAKE_AUTH


def testExpiredSessionTriggersHandshakeBeforeCall(makeClient, seedCredentials, seedSession, handshakePayload):
    seedCredentials()
    seedSession(auth="stale", sessionExpire="2000-01-01T00:00:00+00:00")
    client, transport = makeClient([handshakePayload, pingOk(handshakePayload)])
    result = client.ping()
    assert result.authenticated is True
    assert [r["params"]["action"] for r in transport.requests] == ["handshake", "ping"]
    assert transport.requests[1]["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH


def testReauthOn4701RetriesOnce(dbPath, makeClient, seedCredentials, seedSession, handshakePayload):
    seedCredentials()
    seedSession(auth="expiredtoken")
    client, transport = makeClient([ERROR_4701, handshakePayload, pingOk(handshakePayload)])
    result = client.ping()
    assert result.authenticated is True
    assert len(transport.requests) == 3
    first, second, third = transport.requests
    assert first["params"]["action"] == "ping"
    assert first["headers"]["Authorization"] == "Bearer expiredtoken"
    assert second["params"]["action"] == "handshake"
    assert second["params"]["user"] == "user"
    assert len(second["params"]["auth"]) == 64  # passphrase; handshake has no session yet
    assert second["params"]["timestamp"].isdigit()
    assert "Authorization" not in second["headers"]
    assert third["params"]["action"] == "ping"
    assert third["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    session = SessionRepository(Database(dbPath)).getSession()
    assert session.auth == HANDSHAKE_AUTH


def testApiErrorMapsToTypedException(makeClient, seedCredentials, seedSession):
    seedCredentials()
    seedSession()
    client, _ = makeClient([ERROR_4704])
    with pytest.raises(NotFoundError):
        client.ping()
