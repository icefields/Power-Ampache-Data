# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Auth composition against the known-good vector (CONVENTIONS: auth test)."""
from ampachedata.data.auth.Handshake import buildPassphrase, sha256Hex
from ampachedata.data.auth.SessionManager import SessionManager
from ampachedata.data.db.Database import Database
from ampachedata.data.db.repositories.CredentialsRepository import CredentialsRepository
from ampachedata.data.db.repositories.SessionRepository import SessionRepository
from ampachedata.domain.Credentials import Credentials

KEY = "2a97516c354b68848cdbd8f54a226a0a55b21ed138e207ad6c5cbb9c00aa5aea"
EXPECTED_PASSPHRASE = "53ec985108e46054a949f8d5c609797690711ba0571bdef28b8226e1aa845034"


def testKeyIsSha256OfPassword():
    assert sha256Hex("demo") == KEY


def testPassphraseComposition():
    assert buildPassphrase("1700000000", KEY) == EXPECTED_PASSPHRASE


class _RecordingTransport:
    """Minimal Transport double: hands back one canned payload and records
    the request it was sent (no network, no queue)."""

    def __init__(self, payload):
        self._payload = payload
        self.request = None

    def send(self, method, url, params, headers):
        self.request = {
            "method": method,
            "url": url,
            "params": dict(params),
            "headers": dict(headers),
        }
        return self._payload


def testHandshakeRequestOmitsVersionParam(dbPath, handshakePayload):
    """The handshake request is composed ONLY from CredentialsEntity fields —
    serverUrl, username, and the SHA256(timestamp + stored hash) passphrase —
    and carries no version param. The response's auth becomes the session
    token through the write-through read-back."""
    credentials = Credentials(
        username="user",
        passwordHash=KEY,
        authToken="",
        serverUrl="https://demo.ampache.dev",
    )
    database = Database(dbPath)
    credentialsRepository = CredentialsRepository(database)
    credentialsRepository.upsertCredentials(credentials)
    transport = _RecordingTransport(handshakePayload)
    manager = SessionManager(
        transport, SessionRepository(database), credentialsRepository
    )
    token = manager.ensureSession()
    assert token == handshakePayload["auth"]
    request = transport.request
    assert request["url"] == "https://demo.ampache.dev/server/json.server.php"
    params = request["params"]
    assert params["action"] == "handshake"
    assert params["user"] == "user"
    assert params["timestamp"].isdigit()
    assert len(params["auth"]) == 64  # passphrase, never the session token
    assert params["auth"] == buildPassphrase(params["timestamp"], KEY)
    assert "version" not in params
    database.close()
