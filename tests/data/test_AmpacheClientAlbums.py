"""albums/album write-through flows through the fake transport. No network.

albums returns an `album` list; album returns a single BARE object. Both
write AlbumEntity rows first and read back from the DB only. include=songs
nests `tracks`: song rows (and HistoryEntity rows for played songs only)
are upserted in the same transaction."""
import json
import sqlite3

import pytest

from ampachedata import AmpacheClient, NotFoundError
from ampachedata.data.db.Database import Database
from ampachedata.data.db.repositories.AlbumRepository import AlbumRepository

HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"

ERROR_4704 = {"error": {"code": 4704, "message": "Not found"}}


def testGetAlbumsWriteThroughAndReadBack(dbPath, makeClient, seedCredentials, seedSession,
                                         albumsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([albumsPayload])
    albums = client.getAlbums()
    assert [a.name for a in albums] == ["Sensorisk Deprivation"]
    first = albums[0]
    assert first.id == "7"
    assert first.artistId == "13"
    assert first.artistName == "IOK-1"
    assert first.year == 2011
    assert first.songCount == 4
    assert json.loads(first.genre) == albumsPayload["album"][0]["genre"]
    (request,) = transport.requests
    assert request["params"]["action"] == "albums"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    # write-through: the row is in the DB, not just the return value
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM AlbumEntity").fetchone()[0] == 1


def testGetAlbumsSendsListParams(makeClient, seedCredentials, seedSession, albumsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([albumsPayload])
    client.getAlbums(filter="nausea", exact=1, add="2020-09-16", update="2021-01-01",
                     offset=10, limit=5, cond="year,2012", sort="name")
    params = transport.requests[0]["params"]
    assert params["filter"] == "nausea"
    assert params["exact"] == "1"
    assert params["add"] == "2020-09-16"
    assert params["update"] == "2021-01-01"
    assert params["offset"] == "10"
    assert params["limit"] == "5"
    assert params["cond"] == "year,2012"
    assert params["sort"] == "name"


def testGetAlbumsReadBackOrderedByYearThenSearchName(dbPath, makeClient, seedCredentials,
                                                     seedSession):
    """Ordering comes from the DB (year, searchName), not response order."""
    seedCredentials()
    seedSession()
    payload = {
        "total_count": 3,
        "album": [
            {"id": "1", "name": "Beta", "year": 2012,
             "artist": {"id": "9", "name": "A"}},
            {"id": "2", "name": "Gamma", "year": 2005,
             "artist": {"id": "9", "name": "A"}},
            {"id": "3", "name": "Alpha", "year": 2012,
             "artist": {"id": "9", "name": "A"}},
        ],
    }
    client, _ = makeClient([payload])
    albums = client.getAlbums()
    assert [a.name for a in albums] == ["Gamma", "Alpha", "Beta"]


def testGetAlbumsPaginatesUntilTotalCount(dbPath, makeClient, seedCredentials, seedSession,
                                          albumsPayload, monkeypatch):
    """No offset/limit: full pages keep fetching until offset reaches
    total_count. Rows from EVERY page land in the DB in one transaction."""
    seedCredentials()
    seedSession()
    monkeypatch.setattr(AmpacheClient, "_DEFAULT_PAGE_LIMIT", 2)
    album = albumsPayload["album"][0]
    pageOne = {"total_count": 3, "album": [album, dict(album, id="8", name="Second", year=2012)]}

    def sparseAlbum(albumId, name, year):
        # Sparse payload: only the keys the mapper actually reads.
        return {"id": albumId, "name": name, "year": year,
                "artist": {"id": "13", "name": "IOK-1"}}

    pageTwo = {"total_count": 3, "album": [sparseAlbum("9", "Third", 2013)]}
    client, transport = makeClient([pageOne, pageTwo])
    albums = client.getAlbums()
    assert [a.id for a in albums] == ["7", "8", "9"]
    assert [r["params"]["offset"] for r in transport.requests] == ["0", "2"]
    assert [r["params"]["limit"] for r in transport.requests] == ["2", "2"]
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM AlbumEntity").fetchone()[0] == 3


def testGetAlbumsSparseAlbumNoKeyError(dbPath, makeClient, seedCredentials, seedSession):
    """A sparse album (missing optional keys) maps and persists without KeyError."""
    seedCredentials()
    seedSession()
    payload = {"total_count": 1, "album": [{"id": "42", "name": "Sparse"}]}
    client, _ = makeClient([payload])
    albums = client.getAlbums()
    assert [a.name for a in albums] == ["Sparse"]
    assert albums[0].artistId == ""
    assert albums[0].year == 0


def testGetAlbumWriteThroughAndReadBack(dbPath, makeClient, seedCredentials, seedSession,
                                        albumPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([albumPayload])
    album = client.getAlbum("12")
    assert album.id == "12"
    assert album.name == "Buried in Nausea"
    assert album.artistId == "19"
    assert album.artistName == "Various Artists"
    assert album.year == 2012
    assert album.songCount == 9
    assert json.loads(album.genre) == albumPayload["genre"]
    assert json.loads(album.artists) == albumPayload["artists"]
    (request,) = transport.requests
    assert request["params"]["action"] == "album"
    assert request["params"]["filter"] == "12"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    # write-through: the row is in the DB, not just the return value
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM AlbumEntity").fetchone()[0] == 1
    # the nested `artist` is a partial reference — never upserted
    assert connection.execute("SELECT COUNT(*) FROM ArtistEntity").fetchone()[0] == 0


def testGetAlbumIncludeSongsPersistsNestedRows(dbPath, makeClient, seedCredentials, seedSession,
                                               albumPayload, songsPayload):
    """include=songs nests `tracks`: song rows (and history rows for played
    songs only) are upserted in the same transaction as the album row."""
    seedCredentials()
    seedSession()
    payload = dict(albumPayload)
    payload["tracks"] = songsPayload["song"]
    client, transport = makeClient([payload])
    album = client.getAlbum("12", include="songs")
    assert album.id == "12"
    assert transport.requests[0]["params"]["include"] == "songs"
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM AlbumEntity").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 4
    # fixture songs are never played (null last_played) -> no history rows
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 0


def testGetAlbumNotFoundMapsToNotFoundError(makeClient, seedCredentials, seedSession):
    seedCredentials()
    seedSession()
    client, _ = makeClient([ERROR_4704])
    with pytest.raises(NotFoundError):
        client.getAlbum("999")
