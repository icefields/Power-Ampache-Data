"""Shared fixtures: scratch DB built from docs/schema.sql (tests may create schema —
the library never does), FakeTransport (no network), seed helpers."""
import json
import sqlite3
from pathlib import Path

import pytest

from ampachedata import AmpacheClient
from ampachedata.data.db.Database import Database
from ampachedata.data.db.mappers.SessionMapper import mapSession
from ampachedata.data.db.repositories.CredentialsRepository import CredentialsRepository
from ampachedata.data.db.repositories.SessionRepository import SessionRepository
from ampachedata.domain.Credentials import Credentials

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = REPO_ROOT / "docs" / "schema.sql"
EXAMPLES_DIR = REPO_ROOT / "docs" / "examples"

DEMO_PASSWORD_HASH = "2a97516c354b68848cdbd8f54a226a0a55b21ed138e207ad6c5cbb9c00aa5aea"
HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"


class FakeTransport:
    """Queued-response Transport. Records every request; never touches the network."""

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.requests = []

    def send(self, method, url, params, headers):
        self.requests.append(
            {"method": method, "url": url, "params": dict(params), "headers": dict(headers)}
        )
        if not self._payloads:
            raise AssertionError("FakeTransport received an unexpected request: " + url)
        return self._payloads.pop(0)


@pytest.fixture
def dbPath(tmp_path):
    path = tmp_path / "musicdb.db"
    connection = sqlite3.connect(str(path))
    connection.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    connection.close()
    return str(path)


@pytest.fixture
def handshakePayload():
    return json.loads((EXAMPLES_DIR / "handshake.json").read_text(encoding="utf-8"))


@pytest.fixture
def artistsPayload():
    return json.loads((EXAMPLES_DIR / "artists.json").read_text(encoding="utf-8"))


@pytest.fixture
def artistPayload():
    return json.loads((EXAMPLES_DIR / "artist.json").read_text(encoding="utf-8"))


@pytest.fixture
def albumPayload():
    return json.loads((EXAMPLES_DIR / "album.json").read_text(encoding="utf-8"))


@pytest.fixture
def albumsPayload():
    return json.loads((EXAMPLES_DIR / "albums.json").read_text(encoding="utf-8"))


@pytest.fixture
def artistAlbumsPayload():
    return json.loads((EXAMPLES_DIR / "artist_albums.json").read_text(encoding="utf-8"))


@pytest.fixture
def songPayload():
    return json.loads((EXAMPLES_DIR / "song.json").read_text(encoding="utf-8"))


@pytest.fixture
def songsPayload():
    return json.loads((EXAMPLES_DIR / "songs.json").read_text(encoding="utf-8"))


@pytest.fixture
def makeClient(dbPath):
    def factory(payloads):
        transport = FakeTransport(payloads)
        return AmpacheClient(dbPath=dbPath, transport=transport), transport
    return factory


@pytest.fixture
def seedCredentials(dbPath):
    def seed(serverUrl="https://demo.ampache.dev"):
        database = Database(dbPath)
        CredentialsRepository(database).upsertCredentials(
            Credentials(
                username="user",
                passwordHash=DEMO_PASSWORD_HASH,
                authToken="",
                serverUrl=serverUrl,
            )
        )
        database.close()
    return seed


@pytest.fixture
def seedSession(dbPath, handshakePayload):
    def seed(auth=HANDSHAKE_AUTH, sessionExpire="2999-01-01T00:00:00+00:00"):
        row = mapSession(handshakePayload)
        row["auth"] = auth
        row["sessionExpire"] = sessionExpire
        database = Database(dbPath)
        SessionRepository(database).upsertSession(row)
        database.close()
    return seed
