"""Resurrection flows through the REAL UrllibTransport — only urlopen is
monkeypatched, nothing else is faked. The FakeTransport tests
(test_AmpacheClient.py) bypass the transport entirely, so they cannot catch
envelope-shape bugs; these drive the full wire path the live server
exercises (live_check step [5c]): HTTP 401 carrying the spec-shaped
{'error': {'errorCode': '4701', 'errorMessage': 'Session Expired'}}
envelope -> UrllibTransport normalization -> raiseForError mapping ->
_sendWithAuth's silent re-handshake + single retry."""
import io
import json
import sqlite3
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit

import pytest

from ampachedata import AmpacheClient, InvalidHandshakeError
from ampachedata.data.db.Database import Database
from ampachedata.data.db.repositories.SessionRepository import SessionRepository

URL = "https://demo.ampache.dev/server/json.server.php"
HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"


class _FakeResponse:
    """Minimal urlopen() result: a context manager with a canned read()."""

    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, excType, excValue, traceback):
        return False


def _httpError(code, reason, body):
    return urllib.error.HTTPError(URL, code, reason, None, io.BytesIO(body))


def _patchUlopen(monkeypatch, behaviors):
    """Queue-based urlopen() fake. Each behavior is a 200 body (bytes) or an
    HTTPError raised as-is; once the queue is empty any further request is an
    AssertionError, so a test that must send NOTHING fails loudly if it does.
    Returns the recorded Request objects for wire-level assertions."""
    requests = []

    def fakeUlopen(request, timeout=None):
        requests.append(request)
        if not behaviors:
            raise AssertionError("unexpected request: " + request.full_url)
        behavior = behaviors.pop(0)
        if isinstance(behavior, urllib.error.HTTPError):
            raise behavior
        return _FakeResponse(behavior)

    monkeypatch.setattr(urllib.request, "urlopen", fakeUlopen)
    return requests


def _actions(requests):
    """The action=... value of every recorded request, in order."""
    return [parse_qs(urlsplit(request.full_url).query)["action"][0] for request in requests]


def pingOk(handshakePayload):
    return {
        "auth": handshakePayload["auth"],
        "session_expire": handshakePayload["session_expire"],
        "api": handshakePayload["api"],
    }


def testHttp401SpecEnvelopeResurrectsAndRetriesOnce(dbPath, monkeypatch, seedCredentials,
                                                    seedSession, handshakePayload,
                                                    artistsPayload):
    """The live-server path (live_check [5c]): a dead token with valid format
    and expiry goes out, the server answers HTTP 401 carrying
    {'error': {'errorCode': '4701', 'errorMessage': 'Session Expired'}}.
    UrllibTransport normalizes it to code/message, raiseForError maps '4701'
    to InvalidHandshakeError, and the client silently re-handshakes from the
    stored credentials and retries the original call exactly ONCE."""
    seedCredentials()
    seedSession(auth="deadbeefdeadbeefdeadbeefdeadbeef")
    envelope = json.dumps(
        {"error": {"errorCode": "4701", "errorMessage": "Session Expired"}}
    ).encode("utf-8")
    requests = _patchUlopen(monkeypatch, [
        _httpError(401, "Unauthorized", envelope),
        json.dumps(handshakePayload).encode("utf-8"),
        json.dumps(artistsPayload).encode("utf-8"),
    ])
    client = AmpacheClient(dbPath=dbPath)
    artists = client.getArtists()
    assert [artist.name for artist in artists] == [
        "CARNÚN", "Chi.Otic", "Comedown Kid", "Comfort Fit",
    ]
    assert _actions(requests) == ["artists", "handshake", "artists"]
    first, second, third = requests
    assert first.get_header("Authorization") == "Bearer deadbeefdeadbeefdeadbeefdeadbeef"
    assert "auth=" not in first.full_url  # session token never in the query string
    assert second.get_header("Authorization") is None  # handshake: no session yet
    handshakeQuery = parse_qs(urlsplit(second.full_url).query)
    assert handshakeQuery["user"] == ["user"]
    assert len(handshakeQuery["auth"][0]) == 64  # passphrase, not a session token
    assert handshakeQuery["timestamp"][0].isdigit()
    assert third.get_header("Authorization") == "Bearer " + HANDSHAKE_AUTH
    session = SessionRepository(Database(dbPath)).getSession()
    assert session.auth == HANDSHAKE_AUTH  # dead token replaced by overwrite
    count = sqlite3.connect(dbPath).execute("SELECT COUNT(*) FROM ArtistEntity").fetchone()[0]
    assert count == 4  # the retried call's write-through still happened


def testHttp401EmptyBodyResurrectsAndRetriesOnce(dbPath, monkeypatch, seedCredentials,
                                                 seedSession, handshakePayload):
    """Plain HTTP 401 with an empty body: the transport synthesizes
    {'error': {'code': 401, ...}}, raiseForError maps it to
    InvalidHandshakeError, and ping is silently retried once on the fresh
    token."""
    seedCredentials()
    seedSession(auth="expiredtoken")
    requests = _patchUlopen(monkeypatch, [
        _httpError(401, "Unauthorized", b""),
        json.dumps(handshakePayload).encode("utf-8"),
        json.dumps(pingOk(handshakePayload)).encode("utf-8"),
    ])
    client = AmpacheClient(dbPath=dbPath)
    result = client.ping()
    assert result.authenticated is True
    assert result.auth == HANDSHAKE_AUTH
    assert _actions(requests) == ["ping", "handshake", "ping"]
    assert requests[0].get_header("Authorization") == "Bearer expiredtoken"
    assert requests[2].get_header("Authorization") == "Bearer " + HANDSHAKE_AUTH
    session = SessionRepository(Database(dbPath)).getSession()
    assert session.auth == HANDSHAKE_AUTH


def testHttp403ResurrectsAndRetriesOnce(dbPath, monkeypatch, seedCredentials,
                                         seedSession, handshakePayload):
    """HTTP 403 behaves like 401/4701 through the real transport: silent
    re-handshake from the stored credentials, retry once, session row
    replaced."""
    seedCredentials()
    seedSession(auth="expiredtoken")
    requests = _patchUlopen(monkeypatch, [
        _httpError(403, "Forbidden", b""),
        json.dumps(handshakePayload).encode("utf-8"),
        json.dumps(pingOk(handshakePayload)).encode("utf-8"),
    ])
    client = AmpacheClient(dbPath=dbPath)
    result = client.ping()
    assert result.authenticated is True
    assert _actions(requests) == ["ping", "handshake", "ping"]
    session = SessionRepository(Database(dbPath)).getSession()
    assert session.auth == HANDSHAKE_AUTH


def testGoodbyeTerminatedClientRaisesBeforeAnyRequest(dbPath, monkeypatch, seedCredentials,
                                                       seedSession, goodbyePayload):
    """Deliberate logout is NOT resurrected: after goodbye() the
    terminated-session guard in ensureSession() raises InvalidHandshakeError
    BEFORE any request — urlopen is never called again (no re-handshake, no
    retry), unlike the stale-token resurrections above."""
    seedCredentials()
    seedSession()
    requests = _patchUlopen(monkeypatch, [json.dumps(goodbyePayload).encode("utf-8")])
    client = AmpacheClient(dbPath=dbPath)
    client.goodbye()
    assert _actions(requests) == ["goodbye"]
    with pytest.raises(InvalidHandshakeError):
        client.getArtists(limit=1)
    assert _actions(requests) == ["goodbye"]  # zero new traffic
