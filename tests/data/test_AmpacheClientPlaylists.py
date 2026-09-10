# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""playlists/playlist/playlist_songs write-through flows through the fake
transport. No network.

playlists returns a `playlist` list; playlist returns a single BARE object.
playlist_songs returns a `song` list whose entries carry `playlisttrack` —
stored verbatim as PlaylistSongEntity.position, the ordering contract:
songs + join rows (+ HistoryEntity rows for played songs only) are upserted
in ONE transaction and the read-back orders by position."""
import sqlite3

import pytest

from ampachedata import AmpacheClient, NotFoundError

HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"

ERROR_4704 = {"error": {"code": 4704, "message": "Not found"}}


def testGetPlaylistsWriteThroughAndReadBack(dbPath, makeClient, seedCredentials, seedSession,
                                            playlistsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([playlistsPayload])
    playlists = client.getPlaylists()
    assert [p.name for p in playlists] == ["random - user - private"]
    first = playlists[0]
    assert first.id == "4"
    assert first.owner == "user"
    assert first.items == 43
    assert first.type == "private"
    assert first.artUrl == "https://music.com.au/images/blankalbum_128x128.png"
    (request,) = transport.requests
    assert request["params"]["action"] == "playlists"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM PlaylistEntity").fetchone()[0] == 1
    # the `user` summary object is a partial reference — never upserted
    assert connection.execute("SELECT COUNT(*) FROM UserEntity").fetchone()[0] == 0


def testGetPlaylistsSendsListParams(makeClient, seedCredentials, seedSession, playlistsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([playlistsPayload])
    client.getPlaylists(filter="random", hideSearch=1, showDupes=1, exact=1,
                        add="2020-09-16", update="2021-01-01", offset=10, limit=5,
                        cond="type,public", sort="name")
    params = transport.requests[0]["params"]
    assert params["filter"] == "random"
    assert params["hide_search"] == "1"
    assert params["show_dupes"] == "1"
    assert params["exact"] == "1"
    assert params["add"] == "2020-09-16"
    assert params["update"] == "2021-01-01"
    assert params["offset"] == "10"
    assert params["limit"] == "5"
    assert params["cond"] == "type,public"
    assert params["sort"] == "name"


def testGetPlaylistsPaginatesUntilTotalCount(dbPath, makeClient, seedCredentials, seedSession,
                                             playlistsPayload, monkeypatch):
    """No offset/limit: full pages keep fetching until a short page arrives.
    Rows from EVERY page land in the DB in one transaction."""
    seedCredentials()
    seedSession()
    monkeypatch.setattr(AmpacheClient, "_DEFAULT_PAGE_LIMIT", 2)
    playlist = playlistsPayload["playlist"][0]
    pageOne = {"total_count": 3, "playlist": [
        dict(playlist, id="4", name="Alpha"), dict(playlist, id="5", name="Beta"),
    ]}
    pageTwo = {"total_count": 3, "playlist": [{"id": "6", "name": "Gamma"}]}
    client, transport = makeClient([pageOne, pageTwo])
    playlists = client.getPlaylists()
    assert [p.id for p in playlists] == ["4", "5", "6"]  # read-back: name order
    assert [r["params"]["offset"] for r in transport.requests] == ["0", "2"]
    assert [r["params"]["limit"] for r in transport.requests] == ["2", "2"]
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM PlaylistEntity").fetchone()[0] == 3


def testGetPlaylistWriteThroughAndReadBack(dbPath, makeClient, seedCredentials, seedSession,
                                           playlistPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([playlistPayload])
    playlist = client.getPlaylist("127")
    assert playlist.id == "127"
    assert playlist.name == "renamejson"
    assert playlist.owner == "user"
    assert playlist.items == 0
    assert playlist.type == "private"
    (request,) = transport.requests
    assert request["params"]["action"] == "playlist"
    assert request["params"]["filter"] == "127"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM PlaylistEntity").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM UserEntity").fetchone()[0] == 0


def testGetPlaylistNotFoundMapsToNotFoundError(makeClient, seedCredentials, seedSession):
    seedCredentials()
    seedSession()
    client, _ = makeClient([ERROR_4704])
    with pytest.raises(NotFoundError):
        client.getPlaylist("999")


def testGetSongsFromPlaylistWriteThroughAndReadBack(dbPath, makeClient, seedCredentials,
                                                    seedSession, playlistSongsPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([playlistSongsPayload])
    songs = client.getSongsFromPlaylist("4")
    # position order == payload order for this fixture (playlisttrack 1..4)
    assert [s.id for s in songs] == ["91", "101", "62", "89"]
    assert [s.title for s in songs] == [
        "Home Capsules", "Rehearsal Tape (1996)", "PurpleSmoke", "Stolen",
    ]
    (request,) = transport.requests
    assert request["params"]["action"] == "playlist_songs"
    assert request["params"]["filter"] == "4"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    # total_count (41) exceeds the array (4): the short page ends pagination
    # after ONE request — the fixture is ground truth, not a bug.
    assert client.lastPayload["total_count"] == 41
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 4
    # the join rows: (id, songId, playlistId, position) — position verbatim
    assert connection.execute(
        "SELECT id, songId, playlistId, position FROM PlaylistSongEntity ORDER BY position"
    ).fetchall() == [
        ("4:91", "91", "4", 1),
        ("4:101", "101", "4", 2),
        ("4:62", "62", "4", 3),
        ("4:89", "89", "4", 4),
    ]
    # exactly two fixture songs have a real last_played -> TWO history rows
    assert connection.execute(
        "SELECT mediaId, playCount, lastPlayed FROM HistoryEntity ORDER BY lastPlayed"
    ).fetchall() == [("62", 1, 1751341765000), ("101", 1, 1751342645000)]


def testGetSongsFromPlaylistPositionIsTheOrderingContract(dbPath, makeClient, seedCredentials,
                                                          seedSession):
    """Array order != position order: positions are stored verbatim and the
    read-back orders by them — never renumbered, never payload order."""
    seedCredentials()
    seedSession()
    payload = {"total_count": 3, "song": [
        {"id": "1", "title": "Third", "playlisttrack": 3},
        {"id": "2", "title": "First", "playlisttrack": 1},
        {"id": "3", "title": "Second", "playlisttrack": 2},
    ]}
    client, _ = makeClient([payload])
    songs = client.getSongsFromPlaylist("9")
    assert [s.title for s in songs] == ["First", "Second", "Third"]
    connection = sqlite3.connect(dbPath)
    assert connection.execute(
        "SELECT songId, position FROM PlaylistSongEntity ORDER BY position"
    ).fetchall() == [("2", 1), ("3", 2), ("1", 3)]


def testGetSongsFromPlaylistSendsParams(makeClient, seedCredentials, seedSession,
                                        playlistSongsPayload):
    """Caller-specified random/offset/limit: the window goes out verbatim,
    once — no auto-pagination."""
    seedCredentials()
    seedSession()
    client, transport = makeClient([playlistSongsPayload])
    client.getSongsFromPlaylist("4", random=1, offset=10, limit=5)
    params = transport.requests[0]["params"]
    assert params["action"] == "playlist_songs"
    assert params["filter"] == "4"
    assert params["random"] == "1"
    assert params["offset"] == "10"
    assert params["limit"] == "5"


def testGetSongsFromPlaylistRefetchRefreshesPositions(dbPath, makeClient, seedCredentials,
                                                      seedSession, playlistSongsPayload):
    """Re-fetching the same playlist: join-row ids are synthesized as
    "{playlistId}:{songId}", so INSERT OR REPLACE updates positions in
    place — never duplicates."""
    seedCredentials()
    seedSession()
    reordered = {"total_count": 4, "song": [
        dict(song, playlisttrack=index)
        for index, song in enumerate(reversed(playlistSongsPayload["song"]), start=1)
    ]}
    client, _ = makeClient([playlistSongsPayload, reordered])
    client.getSongsFromPlaylist("4")
    songs = client.getSongsFromPlaylist("4")
    assert [s.id for s in songs] == ["89", "62", "101", "91"]
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM PlaylistSongEntity").fetchone()[0] == 4
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 4
