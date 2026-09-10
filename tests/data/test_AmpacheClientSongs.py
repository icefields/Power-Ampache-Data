# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""songs/song write-through flows through the fake transport. No network.

A song with a real last_played also writes a HistoryEntity row (playCount;
lastPlayed as epoch ms) in the same transaction as the SongEntity row.
Never-played songs (null last_played) write NO history row — epoch-0 rows
are never emitted."""
import json
import sqlite3

import pytest

from ampachedata import AmpacheClient, NotFoundError
from ampachedata.data.db.Database import Database
from ampachedata.data.db.repositories.HistoryRepository import HistoryRepository

HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"

ERROR_4704 = {"error": {"code": 4704, "message": "Not found"}}


def testGetSongsWriteThroughAndReadBack(dbPath, makeClient, seedCredentials, seedSession, songsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([songsPayload])
    songs = client.getSongs()
    assert [s.title for s in songs] == [
        "Are we going Crazy",
        "Arrest Me",
        "As Pure as Possible",
        "Beq Ultra Fat",
    ]
    first = songs[0]
    assert first.id == "115"
    assert first.albumId == "12"
    assert first.artistName == "Chi.Otic"
    assert json.loads(first.genre) == songsPayload["song"][0]["genre"]
    (request,) = transport.requests
    assert request["params"]["action"] == "songs"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    # write-through: rows are in the DB, not just the return value
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 4
    # all fixture songs have null last_played -> never played -> NO history rows
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 0


def testGetSongsSendsListParams(makeClient, seedCredentials, seedSession, songsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([songsPayload])
    client.getSongs(filter="hairy", exact=1, add="2020-09-16", update="2021-01-01",
                    offset=10, limit=5, cond="year,2005", sort="title")
    params = transport.requests[0]["params"]
    assert params["filter"] == "hairy"
    assert params["exact"] == "1"
    assert params["add"] == "2020-09-16"
    assert params["update"] == "2021-01-01"
    assert params["offset"] == "10"
    assert params["limit"] == "5"
    assert params["cond"] == "year,2005"
    assert params["sort"] == "title"


def testGetSongsReadBackIsDbDerived(dbPath, makeClient, seedCredentials, seedSession):
    """Ordering comes from the DB (searchTitle), not response order.
    Envelope-only fields stay on lastPayload, unpersisted."""
    seedCredentials()
    seedSession()
    payload = {
        "total_count": 3,
        "md5": "abc",
        "song": [
            {"id": "1", "title": "Beta", "artist": {"id": "27", "name": "Chi.Otic"},
             "album": {"id": "12", "name": "Buried in Nausea"}},
            {"id": "2", "title": "Alpha", "artist": {"id": "27", "name": "Chi.Otic"},
             "album": {"id": "12", "name": "Buried in Nausea"}},
            {"id": "3", "title": "Gamma", "artist": {"id": "27", "name": "Chi.Otic"},
             "album": {"id": "12", "name": "Buried in Nausea"}},
        ],
    }
    client, _ = makeClient([payload])
    songs = client.getSongs()
    assert [s.title for s in songs] == ["Alpha", "Beta", "Gamma"]
    assert client.lastPayload["total_count"] == 3


def testGetSongsPaginatesUntilTotalCount(dbPath, makeClient, seedCredentials, seedSession,
                                         songsPayload, monkeypatch):
    """No offset/limit: full pages keep fetching until offset reaches
    total_count. Song rows from EVERY page land in the DB in one
    transaction."""
    seedCredentials()
    seedSession()
    monkeypatch.setattr(AmpacheClient, "_DEFAULT_PAGE_LIMIT", 2)
    pageOne = {"total_count": 4, "song": songsPayload["song"][:2]}
    pageTwo = {"total_count": 4, "song": songsPayload["song"][2:]}
    client, transport = makeClient([pageOne, pageTwo])
    songs = client.getSongs()
    assert [s.id for s in songs] == ["115", "107", "118", "85"]
    assert [r["params"]["offset"] for r in transport.requests] == ["0", "2"]
    assert [r["params"]["limit"] for r in transport.requests] == ["2", "2"]
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 4
    # fixture songs are never played (null last_played) -> no history rows
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 0


def testGetSongWriteThroughAndReadBack(dbPath, makeClient, seedCredentials, seedSession, songPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([songPayload])
    song = client.getSong("132")
    assert song.id == "132"  # API id lands in mediaId — SongEntity's actual PK
    assert song.title == "Hairy Crushed Nuts"
    assert song.albumId == "21"
    assert song.albumName == "Forget and Remember"
    assert song.artistId == "36"
    assert song.artistName == "Comfort Fit"
    assert song.albumArtist == "Comfort Fit"
    assert song.songUrl == songPayload["url"]
    assert json.loads(song.genre) == songPayload["genre"]
    assert json.loads(song.artists) == songPayload["artists"]
    assert song.bitrate == 248806
    assert song.trackNumber == 15
    assert song.year == 2005
    assert song.mbId == "db672da0-963b-45a4-b3d8-23efc9c1953d"
    assert song.replayGainTrackGain is None  # nullable passthrough stays null
    (request,) = transport.requests
    assert request["params"]["action"] == "song"
    assert request["params"]["filter"] == "132"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    # write-through: the row is in the DB, not just the return value
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 1
    # null last_played -> never played -> NO HistoryEntity row
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 0


def testGetSongHistoryRowFromLastPlayed(dbPath, makeClient, seedCredentials, seedSession, songPayload):
    """Fixture as-is (null last_played): the song was never played, so NO
    HistoryEntity row is written — never an epoch-0 row."""
    seedCredentials()
    seedSession()
    client, _ = makeClient([songPayload])
    client.getSong("132")
    historyRows = sqlite3.connect(dbPath).execute(
        "SELECT mediaId, playCount, lastPlayed FROM HistoryEntity"
    ).fetchall()
    assert historyRows == []


def testGetSongNotFoundMapsToNotFoundError(makeClient, seedCredentials, seedSession):
    seedCredentials()
    seedSession()
    client, _ = makeClient([ERROR_4704])
    with pytest.raises(NotFoundError):
        client.getSong("999")


def testHistoryReadBackOrderedByLastPlayed(dbPath, makeClient, seedCredentials, seedSession):
    """Play-history ordering is DB-derived: HistoryEntity.lastPlayed DESC."""
    seedCredentials()
    seedSession()
    payload = {
        "song": [
            {"id": "1", "title": "Old Play", "playcount": 2,
             "last_played": "2020-01-01T00:00:00+00:00"},
            {"id": "2", "title": "Recent Play", "playcount": 9,
             "last_played": "2026-01-01T00:00:00+00:00"},
            {"id": "3", "title": "Never Played", "playcount": 0, "last_played": None},
        ],
    }
    client, _ = makeClient([payload])
    client.getSongs()
    histories = HistoryRepository(Database(dbPath)).getHistories()
    # "Never Played" (null last_played) writes no row at all
    assert [(h.mediaId, h.playCount, h.lastPlayed) for h in histories] == [
        ("2", 9, 1767225600000),
        ("1", 2, 1577836800000),
    ]
