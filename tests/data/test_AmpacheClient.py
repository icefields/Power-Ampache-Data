"""ping + re-auth flows through the fake transport. No network."""
import json
import sqlite3

import pytest

from ampachedata import AmpacheClient, InvalidHandshakeError, NotFoundError
from ampachedata.data.db.Database import Database
from ampachedata.data.db.repositories.SessionRepository import SessionRepository
from ampachedata.data.errors import raiseForError

HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"

ANONYMOUS_PING = {"server": "Ampache", "version": "8.0.0", "compatible": "1", "api": "8.0.0"}
ERROR_401 = {"error": {"code": 401, "message": "Unauthorized"}}
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


def testHttp401MapsToInvalidHandshakeError():
    """Direct mapping check: a 401-coded envelope raises InvalidHandshakeError."""
    with pytest.raises(InvalidHandshakeError):
        raiseForError(ERROR_401)


def testHttp401TriggersReauthAndRetry(dbPath, makeClient, seedCredentials, seedSession, handshakePayload):
    """Client-level: a 401 on an authenticated call behaves like 4701 —
    silent re-auth from stored credentials, retry once."""
    seedCredentials()
    seedSession(auth="expiredtoken")
    client, transport = makeClient([ERROR_401, handshakePayload, pingOk(handshakePayload)])
    result = client.ping()
    assert result.authenticated is True
    assert [r["params"]["action"] for r in transport.requests] == ["ping", "handshake", "ping"]
    session = SessionRepository(Database(dbPath)).getSession()
    assert session.auth == HANDSHAKE_AUTH


def testGetArtistsWriteThroughAndReadBack(dbPath, makeClient, seedCredentials, seedSession, artistsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([artistsPayload])
    artists = client.getArtists()
    assert [a.name for a in artists] == ["CARNÚN", "Chi.Otic", "Comedown Kid", "Comfort Fit"]
    (request,) = transport.requests
    assert request["params"]["action"] == "artists"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    # write-through: rows are in the DB, not just the return value
    count = sqlite3.connect(dbPath).execute("SELECT COUNT(*) FROM ArtistEntity").fetchone()[0]
    assert count == 4


def testGetArtistsSendsListParams(makeClient, seedCredentials, seedSession, artistsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([artistsPayload])
    client.getArtists(filter="comfort", exact=1, offset=10, limit=5, sort="name", cond="and")
    params = transport.requests[0]["params"]
    assert params["filter"] == "comfort"
    assert params["exact"] == "1"
    assert params["offset"] == "10"
    assert params["limit"] == "5"
    assert params["sort"] == "name"
    assert params["cond"] == "and"


def testGetArtistsPaginatesUntilShortPage(dbPath, makeClient, seedCredentials, seedSession,
                                          artistsPayload, monkeypatch):
    """No offset/limit: _fetchAllPages keeps fetching pages of
    _DEFAULT_PAGE_LIMIT rows until a SHORT page ends the loop (total_count
    not yet reached). Rows from every page are persisted; the read-back
    still comes only from the DB."""
    seedCredentials()
    seedSession()
    monkeypatch.setattr(AmpacheClient, "_DEFAULT_PAGE_LIMIT", 2)
    pageOne = {"total_count": 3, "artist": artistsPayload["artist"][:2]}
    pageTwo = {"total_count": 3, "artist": artistsPayload["artist"][2:3]}
    client, transport = makeClient([pageOne, pageTwo])
    artists = client.getArtists()
    assert [a.name for a in artists] == ["CARNÚN", "Chi.Otic", "Comedown Kid"]
    assert [r["params"]["offset"] for r in transport.requests] == ["0", "2"]
    assert [r["params"]["limit"] for r in transport.requests] == ["2", "2"]
    # write-through: every page's rows are in the DB
    count = sqlite3.connect(dbPath).execute("SELECT COUNT(*) FROM ArtistEntity").fetchone()[0]
    assert count == 3


def testGetArtistWriteThroughAndReadBack(dbPath, makeClient, seedCredentials, seedSession, artistPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([artistPayload])
    artist = client.getArtist("14")
    assert artist.id == "14"
    assert artist.name == "Nofi/found."
    assert artist.albumCount == 1
    assert artist.songCount == 11
    assert json.loads(artist.genre) == artistPayload["genre"]
    assert artist.artUrl == "https://music.com.au/images/blankalbum_128x128.png"
    assert artist.time == 4423
    (request,) = transport.requests
    assert request["params"]["action"] == "artist"
    assert request["params"]["filter"] == "14"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    # write-through: the row is in the DB, not just the return value
    count = sqlite3.connect(dbPath).execute("SELECT COUNT(*) FROM ArtistEntity").fetchone()[0]
    assert count == 1


def testGetArtistIncludePersistsNestedRows(dbPath, makeClient, seedCredentials, seedSession,
                                           artistPayload, albumPayload, songPayload):
    """include=1: nested albums/songs are normalized into their own tables in the
    same transaction. Partial references inside them (the album's bare {id, name}
    artist; the song's artist/album/albumartist) are extracted onto their rows but
    never upserted — ArtistEntity keeps exactly one row."""
    seedCredentials()
    seedSession()
    artistPayload["albums"] = [albumPayload]
    artistPayload["songs"] = [songPayload]
    client, transport = makeClient([artistPayload])
    artist = client.getArtist("14", include="albums,songs")
    assert artist.id == "14"
    assert transport.requests[0]["params"]["include"] == "albums,songs"
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM ArtistEntity").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM AlbumEntity").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 1
    album = connection.execute("SELECT id, artistId, artistName FROM AlbumEntity").fetchone()
    assert album[0] == "12"
    assert album[1] == "19"  # partial reference extracted onto the row, not upserted
    assert album[2] == "Various Artists"
    song = connection.execute("SELECT mediaId, albumId, artistId FROM SongEntity").fetchone()
    assert song[0] == "132"  # API id lands in mediaId — SongEntity's actual PK
    assert song[1] == "21"
    assert song[2] == "36"


def testGetArtistNotFoundMapsToNotFoundError(makeClient, seedCredentials, seedSession):
    seedCredentials()
    seedSession()
    client, _ = makeClient([ERROR_4704])
    with pytest.raises(NotFoundError):
        client.getArtist("999")


def testGetAlbumsFromArtistWriteThroughAndReadBack(dbPath, makeClient, seedCredentials, seedSession, artistAlbumsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([artistAlbumsPayload])
    albums = client.getAlbumsFromArtist("14")
    assert len(albums) == 1
    album = albums[0]
    assert album.id == "8"
    assert album.name == "Nofi Devices"
    assert album.artistId == "14"
    assert album.artistName == "Nofi/found."
    assert album.songCount == 11
    assert json.loads(album.genre) == artistAlbumsPayload["album"][0]["genre"]
    (request,) = transport.requests
    assert request["params"]["action"] == "artist_albums"
    assert request["params"]["filter"] == "14"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    # write-through: the row is in the DB, not just the return value
    count = sqlite3.connect(dbPath).execute("SELECT COUNT(*) FROM AlbumEntity").fetchone()[0]
    assert count == 1


def testGetAlbumsFromArtistSendsListParams(makeClient, seedCredentials, seedSession, artistAlbumsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([artistAlbumsPayload])
    client.getAlbumsFromArtist("14", albumArtist=1, offset=10, limit=5, cond="year,2012", sort="name")
    params = transport.requests[0]["params"]
    assert params["filter"] == "14"
    assert params["album_artist"] == "1"
    assert params["offset"] == "10"
    assert params["limit"] == "5"
    assert params["cond"] == "year,2012"
    assert params["sort"] == "name"


def testGetAlbumsFromArtistReadBackIsDbDerived(dbPath, makeClient, seedCredentials, seedSession):
    """Ordering comes from the DB (year, searchName), not response order.
    Envelope-only fields stay on lastPayload, unpersisted."""
    seedCredentials()
    seedSession()
    payload = {
        "total_count": 3,
        "md5": "abc",
        "album": [
            {"id": "1", "name": "Beta", "year": 2001, "artist": {"id": "14", "name": "Nofi/found."}},
            {"id": "2", "name": "Alpha", "year": 2001, "artist": {"id": "14", "name": "Nofi/found."}},
            {"id": "3", "name": "Gamma", "year": 1999, "artist": {"id": "14", "name": "Nofi/found."}},
        ],
    }
    client, _ = makeClient([payload])
    albums = client.getAlbumsFromArtist("14")
    assert [a.name for a in albums] == ["Gamma", "Alpha", "Beta"]
    assert client.lastPayload["total_count"] == 3


def testGetAlbumsFromArtistSparseAlbumNoKeyError(dbPath, makeClient, seedCredentials, seedSession):
    """A sparse album (explicit null artist, missing genre/art/...) flows
    through the full write-through without KeyError."""
    seedCredentials()
    seedSession()
    payload = {"album": [{"id": "42", "name": "Sparse (Demo)", "artist": None}]}
    client, _ = makeClient([payload])
    albums = client.getAlbumsFromArtist("")  # null artist -> artistId ""
    assert len(albums) == 1
    assert albums[0].id == "42"
    assert albums[0].artists == "[]"
    assert albums[0].artUrl == ""
