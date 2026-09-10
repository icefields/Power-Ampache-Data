# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""UrllibTransport's non-2xx handling: HTTP errors come back as error
envelopes carrying the HTTP status as the code, so raiseForError can map
them (401/403 -> InvalidHandshakeError, driving AmpacheClient's silent
re-auth + single retry). urlopen is monkeypatched — no network."""
import io
import json
import urllib.error
import urllib.request

import pytest

from ampachedata.data.Transport import UrllibTransport
from ampachedata.data.errors import InvalidHandshakeError, raiseForError

URL = "https://demo.ampache.dev/server/json.server.php"


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


def _patchUlopen(monkeypatch, behavior):
    """urlopen returns a 200 whose body is `behavior` — or raises it when it
    is an HTTPError instance."""

    def fakeUlopen(request, timeout=None):
        if isinstance(behavior, urllib.error.HTTPError):
            raise behavior
        return _FakeResponse(behavior)

    monkeypatch.setattr(urllib.request, "urlopen", fakeUlopen)


def _httpError(code, reason, body):
    return urllib.error.HTTPError(URL, code, reason, None, io.BytesIO(body))


def testSuccessBodyIsReturnedDecoded(monkeypatch):
    _patchUlopen(monkeypatch, json.dumps({"auth": "token"}).encode("utf-8"))
    payload = UrllibTransport().send("GET", URL, {}, {})
    assert payload == {"auth": "token"}


def testHttp403WithEmptyBodyBecomes403Envelope(monkeypatch):
    _patchUlopen(monkeypatch, _httpError(403, "Forbidden", b""))
    payload = UrllibTransport().send("GET", URL, {}, {})
    assert payload["error"]["code"] == 403
    assert payload["error"]["message"] == "Forbidden"
    with pytest.raises(InvalidHandshakeError):
        raiseForError(payload)


def testHttp403WithHtmlBodyKeepsSnippetAsMessage(monkeypatch):
    _patchUlopen(monkeypatch, _httpError(403, "Forbidden", b"<html>403</html>"))
    payload = UrllibTransport().send("GET", URL, {}, {})
    assert payload["error"]["code"] == 403
    assert "<html>" in payload["error"]["message"]
    with pytest.raises(InvalidHandshakeError):
        raiseForError(payload)


def testHttp401Becomes401Envelope(monkeypatch):
    _patchUlopen(monkeypatch, _httpError(401, "Unauthorized", b""))
    payload = UrllibTransport().send("GET", URL, {}, {})
    assert payload["error"]["code"] == 401
    with pytest.raises(InvalidHandshakeError):
        raiseForError(payload)


def testJsonErrorEnvelopeBodyPassesThroughUnchanged(monkeypatch):
    """The server's own envelope wins over the HTTP status: a 403 carrying a
    spec-code body keeps the spec code (4701 here), not 403."""
    envelope = json.dumps(
        {"error": {"code": 4701, "message": "Invalid handshake"}}
    ).encode("utf-8")
    _patchUlopen(monkeypatch, _httpError(403, "Forbidden", envelope))
    payload = UrllibTransport().send("GET", URL, {}, {})
    assert payload == {"error": {"code": 4701, "message": "Invalid handshake"}}
    with pytest.raises(InvalidHandshakeError) as excinfo:
        raiseForError(payload)
    assert excinfo.value.code == 4701


def testHttp401WithStringErrorCodeEnvelopeIsNormalized(monkeypatch):
    """A spec-shaped envelope (errorCode/errorMessage keys, the code as a
    STRING) on a non-2xx answer is normalized to code/message so
    raiseForError's int() coercion can map it: '4701' -> InvalidHandshakeError,
    driving AmpacheClient's silent re-auth + single retry. This is the live
    server's stale-token answer: HTTP 401 carrying errorCode '4701'."""
    envelope = json.dumps(
        {"error": {"errorCode": "4701", "errorMessage": "Session Expired"}}
    ).encode("utf-8")
    _patchUlopen(monkeypatch, _httpError(401, "Unauthorized", envelope))
    payload = UrllibTransport().send("GET", URL, {}, {})
    assert payload == {"error": {"code": "4701", "message": "Session Expired"}}
    with pytest.raises(InvalidHandshakeError) as excinfo:
        raiseForError(payload)
    assert excinfo.value.code == 4701
