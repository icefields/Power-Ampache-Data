# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""goodbye (session teardown) through the fake transport. No network."""
import sqlite3

import pytest

from ampachedata import InvalidHandshakeError
from ampachedata.data.db.Database import Database
from ampachedata.data.db.repositories.SessionRepository import SessionRepository

HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"
ERROR_4701 = {"error": {"code": 4701, "message": "Invalid handshake"}}


def testGoodbyeSuccessClearsSessionKeepsCredentials(dbPath, makeClient, seedCredentials,
                                                    seedSession, goodbyePayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([goodbyePayload])
    result = client.goodbye()
    assert result.success is True
    assert result.message == goodbyePayload["success"]
    (request,) = transport.requests
    assert request["params"]["action"] == "goodbye"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]  # session token never in the query string
    assert SessionRepository(Database(dbPath)).getSession() is None
    # CredentialsEntity survives — a new client instance can still re-handshake
    count = sqlite3.connect(dbPath).execute(
        "SELECT COUNT(*) FROM CredentialsEntity"
    ).fetchone()[0]
    assert count == 1


def testGoodbyeErrorLeavesSessionIntact(dbPath, makeClient, seedCredentials, seedSession):
    """Error envelope: typed error propagates, session row survives, and NO
    re-auth/retry happens — goodbye never triggers the 4701 flow."""
    seedCredentials()
    seedSession()
    client, transport = makeClient([ERROR_4701])
    with pytest.raises(InvalidHandshakeError):
        client.goodbye()
    assert len(transport.requests) == 1  # no handshake, no retry
    session = SessionRepository(Database(dbPath)).getSession()
    assert session is not None
    assert session.auth == HANDSHAKE_AUTH


def testAuthenticatedCallAfterGoodbyeRaises(dbPath, makeClient, seedCredentials,
                                            seedSession, goodbyePayload):
    """After goodbye, authenticated calls fail with the existing auth error —
    no silent re-handshake (the transport queue is empty; any request would
    raise AssertionError, and we assert none was made)."""
    seedCredentials()
    seedSession()
    client, transport = makeClient([goodbyePayload])
    client.goodbye()
    with pytest.raises(InvalidHandshakeError):
        client.getArtists()
    assert len(transport.requests) == 1  # only goodbye; no handshake attempted


def testGoodbyeWithoutSessionRaises(makeClient, seedCredentials):
    seedCredentials()
    client, transport = makeClient([])
    with pytest.raises(InvalidHandshakeError):
        client.goodbye()
    assert transport.requests == []
