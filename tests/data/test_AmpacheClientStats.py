"""stats song family (type=song) write-through flows through the fake
transport. No network.

recent/frequent/forgotten read back through play history (HistoryEntity) —
DB-derived ordering per CONVENTIONS. random is the explicit CONVENTIONS
exception: random order can't be DB-derived, so the ORDER comes from the
response while entity data still comes only from the DB read-back.

The stats_song.json fixture ships never-played songs (null last_played);
_playedPayload builds played variants, and the raw fixture exercises the
never-played paths (no HistoryEntity row, absent from history read-backs)."""
import copy
import json
import sqlite3

from ampachedata import AmpacheClient

HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"


def _playedPayload(statsSongPayload):
    """Deep copy with real last_played/playcount values — the fixture ships
    never-played songs (null last_played). Song 135 is the recent/frequent
    leader; 134 the laggard."""
    payload = copy.deepcopy(statsSongPayload)
    payload["song"][0]["last_played"] = "2026-01-01T00:00:00+00:00"
    payload["song"][0]["playcount"] = 9
    payload["song"][1]["last_played"] = "2020-01-01T00:00:00+00:00"
    payload["song"][1]["playcount"] = 2
    return payload


def testGetRecentSongsWriteThroughAndReadBack(dbPath, makeClient, seedCredentials,
                                              seedSession, statsSongPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([_playedPayload(statsSongPayload)])
    songs = client.getRecentSongs()
    # read-back order is DB-derived: HistoryEntity.lastPlayed DESC
    assert [s.id for s in songs] == ["135", "134"]
    assert [s.title for s in songs] == ["Emotional Draft", "Swabian Sound System"]
    (request,) = transport.requests
    assert request["params"]["action"] == "stats"
    assert request["params"]["type"] == "song"
    assert request["params"]["filter"] == "recent"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    # write-through: rows are in the DB, not just the return value
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 2


def testGetRecentSongsSendsStatsParams(makeClient, seedCredentials, seedSession, statsSongPayload):
    """user_id/username/offset/limit are forwarded; a caller-specified window
    means ONE request, verbatim (the caller owns the window)."""
    seedCredentials()
    seedSession()
    client, transport = makeClient([statsSongPayload])
    client.getRecentSongs(userId=4, username="user", offset=10, limit=5)
    (request,) = transport.requests
    params = request["params"]
    assert params["action"] == "stats"
    assert params["type"] == "song"
    assert params["filter"] == "recent"
    assert params["user_id"] == "4"
    assert params["username"] == "user"
    assert params["offset"] == "10"
    assert params["limit"] == "5"


def testGetFrequentSongsOrderedByPlayCount(makeClient, seedCredentials, seedSession, statsSongPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([_playedPayload(statsSongPayload)])
    songs = client.getFrequentSongs()
    # read-back order is DB-derived: HistoryEntity.playCount DESC (9 before 2)
    assert [s.id for s in songs] == ["135", "134"]
    assert transport.requests[0]["params"]["filter"] == "frequent"


def testGetForgottenSongsOrderedByLastPlayedAscending(makeClient, seedCredentials, seedSession,
                                                      statsSongPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([_playedPayload(statsSongPayload)])
    songs = client.getForgottenSongs()
    # read-back order is DB-derived: HistoryEntity.lastPlayed ASC (2020 before 2026)
    assert [s.id for s in songs] == ["134", "135"]
    assert transport.requests[0]["params"]["filter"] == "forgotten"


def testGetRandomSongsReadBackInResponseOrder(dbPath, makeClient, seedCredentials, seedSession,
                                               statsSongPayload):
    """CONVENTIONS exception, explicit: random order can't be DB-derived, so
    the ORDER comes from the response — here deliberately the REVERSE of the
    history-derived order — while entity data still comes only from the DB."""
    seedCredentials()
    seedSession()
    payload = _playedPayload(statsSongPayload)
    payload["song"].reverse()  # response order: 134 (2020) before 135 (2026)
    client, transport = makeClient([payload])
    songs = client.getRandomSongs()
    assert [s.id for s in songs] == ["134", "135"]
    assert songs[0].title == "Swabian Sound System"  # entity data from the DB row
    assert transport.requests[0]["params"]["filter"] == "random"
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 2


def testGetRecentSongsEmptyWithoutPlayHistory(dbPath, makeClient, seedCredentials, seedSession,
                                              statsSongPayload):
    """Raw fixture: never-played songs (null last_played) still persist to
    SongEntity, write NO history row, and never appear in the recent
    read-back (it joins HistoryEntity)."""
    seedCredentials()
    seedSession()
    client, _ = makeClient([statsSongPayload])
    assert client.getRecentSongs() == []
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 0


def testStatsSongsWriteHistoryRowsOnlyForPlayedSongs(dbPath, makeClient, seedCredentials,
                                                     seedSession, statsSongPayload):
    """Mixed payload: the played song writes SongEntity + HistoryEntity; the
    never-played one writes SongEntity only — never an epoch-0 history row."""
    seedCredentials()
    seedSession()
    payload = copy.deepcopy(statsSongPayload)
    payload["song"][0]["last_played"] = "2026-01-01T00:00:00+00:00"
    payload["song"][0]["playcount"] = 9
    client, _ = makeClient([payload])
    songs = client.getRecentSongs()
    assert [s.id for s in songs] == ["135"]  # only the played song has history
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 1
    historyRow = connection.execute(
        "SELECT mediaId, playCount, lastPlayed FROM HistoryEntity"
    ).fetchone()
    assert historyRow == ("135", 9, 1767225600000)  # lastPlayed as epoch ms


def testStatsSongsPaginateUntilTotalCount(dbPath, makeClient, seedCredentials, seedSession,
                                          statsSongPayload, monkeypatch):
    """No offset/limit: full pages keep fetching until offset reaches
    total_count. Rows from EVERY page land in the DB in one transaction and
    the read-back spans all pages."""
    seedCredentials()
    seedSession()
    monkeypatch.setattr(AmpacheClient, "_DEFAULT_PAGE_LIMIT", 1)
    payload = _playedPayload(statsSongPayload)
    pageOne = {"total_count": 2, "song": payload["song"][:1]}
    pageTwo = {"total_count": 2, "song": payload["song"][1:]}
    client, transport = makeClient([pageOne, pageTwo])
    songs = client.getRecentSongs()
    assert [s.id for s in songs] == ["135", "134"]
    assert [r["params"]["offset"] for r in transport.requests] == ["0", "1"]
    assert [r["params"]["limit"] for r in transport.requests] == ["1", "1"]
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM SongEntity").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 2


def testStatsSongsMapExampleFields(makeClient, seedCredentials, seedSession, statsSongPayload):
    """Mapper tested against the real example response (CONVENTIONS): stats
    songs map exactly like songs-method songs — same SongMapper."""
    seedCredentials()
    seedSession()
    client, _ = makeClient([statsSongPayload])
    songs = client.getRandomSongs()  # response order = fixture order
    first = songs[0]
    assert first.id == "135"
    assert first.title == "Emotional Draft"
    assert first.albumId == "21"
    assert first.albumName == "Forget and Remember"
    assert first.artistId == "36"
    assert first.artistName == "Comfort Fit"
    assert first.albumArtist == "Comfort Fit"
    assert first.songUrl == statsSongPayload["song"][0]["url"]
    assert json.loads(first.genre) == statsSongPayload["song"][0]["genre"]
    assert json.loads(first.artists) == statsSongPayload["song"][0]["artists"]
    assert first.bitrate == 235925
    assert first.trackNumber == 14
    assert first.year == 2005
    assert first.mbId == "ab598f5a-4cbb-4ce0-a3ac-9de17026f528"
