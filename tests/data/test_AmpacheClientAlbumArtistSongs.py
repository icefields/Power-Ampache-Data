"""album_songs / artist_songs write-through flows through the fake transport.
No network.

Both are scoped song lists: fetch -> map (song rows + HistoryEntity rows for
played songs only) -> upsert BOTH in ONE transaction -> read back from the DB
only (album songs in disk/track order; artist songs by searchTitle). Each
fixture has exactly ONE song with a real last_played, so each write-through
writes exactly ONE HistoryEntity row — never-played songs write none."""
import sqlite3

HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"


def testGetAlbumSongsWriteThroughAndReadBack(dbPath, makeClient, seedCredentials,
                                             seedSession, albumSongsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([albumSongsPayload])
    songs = client.getAlbumSongs("12")
    # DB-derived ordering: disk, then trackNumber (every fixture song is disk 1)
    assert [s.title for s in songs] == [
        "I wanna walk through the fire",
        "He is the Master of War",
        "Dance with the Devil",
        "Representin",
    ]
    first = songs[0]
    assert first.id == "110"
    assert first.albumId == "12"
    assert first.artistName == "Manic Notion"
    assert first.trackNumber == 1
    (request,) = transport.requests
    assert request["params"]["action"] == "album_songs"
    assert request["params"]["filter"] == "12"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    # total_count (9) exceeds the array (4): the short page ends pagination
    # after ONE request — the fixture is ground truth, not a bug.
    assert client.lastPayload["total_count"] == 9
    # write-through: rows are in the DB, not just the return value
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 4
    # exactly one fixture song has a real last_played -> ONE history row
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 1
    assert connection.execute(
        "SELECT mediaId, playCount, lastPlayed FROM HistoryEntity"
    ).fetchall() == [("110", 1, 1751342464000)]


def testGetAlbumSongsSendsListParams(makeClient, seedCredentials, seedSession, albumSongsPayload):
    """Caller-specified offset/limit: the window goes out verbatim, once —
    no auto-pagination."""
    seedCredentials()
    seedSession()
    client, transport = makeClient([albumSongsPayload])
    client.getAlbumSongs("12", offset=10, limit=5, cond="year,2005", sort="title")
    params = transport.requests[0]["params"]
    assert params["action"] == "album_songs"
    assert params["filter"] == "12"
    assert params["offset"] == "10"
    assert params["limit"] == "5"
    assert params["cond"] == "year,2005"
    assert params["sort"] == "title"


def testGetAlbumSongsSparseSong(dbPath, makeClient, seedCredentials, seedSession):
    """mapSong reads every field via .get() — a sparse song (only id/title/
    album) maps without raising, and the scoped read-back finds it by
    albumId. No last_played -> no HistoryEntity row."""
    seedCredentials()
    seedSession()
    payload = {"total_count": 1, "song": [
        {"id": "999", "title": "Sparse", "album": {"id": "7", "name": "B"}},
    ]}
    client, _ = makeClient([payload])
    songs = client.getAlbumSongs("7")
    assert [s.id for s in songs] == ["999"]
    assert songs[0].title == "Sparse"
    assert songs[0].albumId == "7"
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 0


def testGetArtistSongsWriteThroughAndReadBack(dbPath, makeClient, seedCredentials,
                                              seedSession, artistSongsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([artistSongsPayload])
    songs = client.getArtistSongs("13")
    # DB-derived ordering: searchTitle (no parentheses -> normalization is a
    # no-op for these titles)
    assert [s.title for s in songs] == [
        "Galenskap",
        "Sensorisk Deprivation",
        "Vansinne",
        "Vanvett",
    ]
    first = songs[0]
    assert first.id == "81"
    assert first.artistId == "13"
    assert first.artistName == "IOK-1"
    assert first.albumId == "7"
    (request,) = transport.requests
    assert request["params"]["action"] == "artist_songs"
    assert request["params"]["filter"] == "13"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 4
    # exactly one fixture song has a real last_played -> ONE history row
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 1
    assert connection.execute(
        "SELECT mediaId, playCount, lastPlayed FROM HistoryEntity"
    ).fetchall() == [("83", 13, 1614144686000)]


def testGetArtistSongsSendsListParams(makeClient, seedCredentials, seedSession, artistSongsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([artistSongsPayload])
    client.getArtistSongs("13", top50=1, offset=10, limit=5, cond="year,2005", sort="title")
    params = transport.requests[0]["params"]
    assert params["action"] == "artist_songs"
    assert params["filter"] == "13"
    assert params["top50"] == "1"
    assert params["offset"] == "10"
    assert params["limit"] == "5"
    assert params["cond"] == "year,2005"
    assert params["sort"] == "title"


def testGetArtistSongsSparseSong(dbPath, makeClient, seedCredentials, seedSession):
    """Sparse artist payload: mapSong's .get()-only reads mean no key is
    required; the scoped read-back finds the song by artistId."""
    seedCredentials()
    seedSession()
    payload = {"total_count": 1, "song": [
        {"id": "999", "title": "Sparse", "artist": {"id": "13", "name": "IOK-1"}},
    ]}
    client, _ = makeClient([payload])
    songs = client.getArtistSongs("13")
    assert [s.id for s in songs] == ["999"]
    assert songs[0].artistId == "13"
