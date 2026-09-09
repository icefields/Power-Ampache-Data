"""stats (type=album) write-through flows through the fake transport. No network.

filter is ALWAYS sent explicitly (the API default is random — never
inherited). limit semantics come from _fetchAllPages: no limit -> full
pages until total_count; explicit limit -> the caller's window, verbatim.

NO HistoryEntity rows are written for albums: mapHistory is song-shaped
and AlbumEntity has no play columns. Play-derived ordering is therefore
impossible from stored columns — recent/frequent/forgotten read back
ordered by (year, searchName) like getAlbums; newest/highest read back the
same way (LIMITATION: neither add date nor rating orders the read-back);
only random keeps response order (the explicit CONVENTIONS exception)."""
import sqlite3

HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"


def testGetRecentAlbumsWriteThroughAndReadBack(dbPath, makeClient, seedCredentials,
                                               seedSession, statsAlbumPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([statsAlbumPayload])
    albums = client.getRecentAlbums()
    # read-back is (year, searchName): 2005 "Forget and Remember" before 2012 "Buried in Nausea"
    assert [a.id for a in albums] == ["21", "12"]
    first = albums[0]
    assert first.name == "Forget and Remember"
    assert first.artistId == "36"
    assert first.artistName == "Comfort Fit"
    assert first.year == 2005
    assert first.songCount == 20
    (request,) = transport.requests
    assert request["params"]["action"] == "stats"
    assert request["params"]["type"] == "album"
    assert request["params"]["filter"] == "recent"
    assert request["headers"]["Authorization"] == "Bearer " + HANDSHAKE_AUTH
    assert "auth" not in request["params"]
    # write-through: rows are in the DB, not just the return value
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM AlbumEntity").fetchone()[0] == 2
    # albums never write history rows
    assert connection.execute("SELECT COUNT(*) FROM HistoryEntity").fetchone()[0] == 0


def testGetFrequentAlbumsSendsFilterAndReadsBack(makeClient, seedCredentials, seedSession,
                                                 statsAlbumPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([statsAlbumPayload])
    albums = client.getFrequentAlbums()
    assert [a.id for a in albums] == ["21", "12"]
    assert transport.requests[0]["params"]["filter"] == "frequent"


def testGetForgottenAlbumsSendsFilterAndReadsBack(makeClient, seedCredentials, seedSession,
                                                  statsAlbumPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([statsAlbumPayload])
    albums = client.getForgottenAlbums()
    assert [a.id for a in albums] == ["21", "12"]
    assert transport.requests[0]["params"]["filter"] == "forgotten"


def testGetRandomAlbumsKeepsResponseOrder(dbPath, makeClient, seedCredentials,
                                          seedSession, statsAlbumPayload):
    """CONVENTIONS exception: random order can't be DB-derived, so the ORDER
    comes from the response while entity data is read back from the DB by id."""
    seedCredentials()
    seedSession()
    reversedPayload = dict(statsAlbumPayload)
    reversedPayload["album"] = list(reversed(statsAlbumPayload["album"]))
    client, transport = makeClient([reversedPayload])
    albums = client.getRandomAlbums()
    # response order (12 first), NOT the (year, searchName) DB order
    assert [a.id for a in albums] == ["12", "21"]
    assert albums[0].name == "Buried in Nausea"  # entity data from the DB read-back
    assert transport.requests[0]["params"]["filter"] == "random"
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM AlbumEntity").fetchone()[0] == 2


def testStatsAlbumsExplicitLimitPassesThrough(makeClient, seedCredentials, seedSession,
                                              statsAlbumPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([statsAlbumPayload])
    client.getRecentAlbums(limit=10)
    (request,) = transport.requests  # caller's window: single call, verbatim
    assert request["params"]["limit"] == "10"
    assert "offset" not in request["params"]


def testStatsAlbumsOptionalParamsPassThrough(makeClient, seedCredentials, seedSession,
                                             statsAlbumPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([statsAlbumPayload])
    client.getFrequentAlbums(userId=4, username="user", offset=5, limit=10)
    params = transport.requests[0]["params"]
    assert params["user_id"] == "4"
    assert params["username"] == "user"
    assert params["offset"] == "5"
    assert params["limit"] == "10"


def testStatsAlbumsEnvelopeFieldsStayOnLastPayload(dbPath, makeClient, seedCredentials,
                                                   seedSession, statsAlbumPayload):
    seedCredentials()
    seedSession()
    client, _ = makeClient([statsAlbumPayload])
    client.getRecentAlbums()
    assert client.lastPayload["total_count"] == 2
    assert client.lastPayload["md5"] == statsAlbumPayload["md5"]


def testStatsAlbumsUpsertRefreshesNeverDuplicates(dbPath, makeClient, seedCredentials,
                                                  seedSession, statsAlbumPayload):
    seedCredentials()
    seedSession()
    client, _ = makeClient([statsAlbumPayload, statsAlbumPayload])
    client.getRecentAlbums()
    client.getFrequentAlbums()
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM AlbumEntity").fetchone()[0] == 2


def testGetNewestAlbumsSendsFilterAndReadsBack(dbPath, makeClient, seedCredentials,
                                               seedSession, statsAlbumPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([statsAlbumPayload])
    albums = client.getNewestAlbums()
    # read-back is (year, searchName): 2005 "Forget and Remember" before 2012 "Buried in Nausea"
    assert [a.id for a in albums] == ["21", "12"]
    (request,) = transport.requests
    assert request["params"]["action"] == "stats"
    assert request["params"]["type"] == "album"
    assert request["params"]["filter"] == "newest"
    # write-through: rows are in the DB, not just the return value
    connection = sqlite3.connect(dbPath)
    assert connection.execute("SELECT COUNT(*) FROM AlbumEntity").fetchone()[0] == 2


def testGetHighestAlbumsSendsFilterAndReadsBack(makeClient, seedCredentials, seedSession,
                                                statsAlbumPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([statsAlbumPayload])
    albums = client.getHighestAlbums()
    assert [a.id for a in albums] == ["21", "12"]
    assert transport.requests[0]["params"]["filter"] == "highest"


def testNewestAndHighestAlbumsReadBackIsNotResponseOrder(makeClient, seedCredentials,
                                                         seedSession, statsAlbumPayload):
    """LIMITATION, explicit: neither add date (newest) nor rating (highest)
    orders the read-back — it is ALWAYS (year, searchName), even when the
    response order differs (here deliberately reversed). Contrast
    testGetRandomAlbumsKeepsResponseOrder: only random keeps response order."""
    seedCredentials()
    seedSession()
    reversedPayload = dict(statsAlbumPayload)
    reversedPayload["album"] = list(reversed(statsAlbumPayload["album"]))
    client, _ = makeClient([reversedPayload, reversedPayload])
    assert [a.id for a in client.getNewestAlbums()] == ["21", "12"]
    assert [a.id for a in client.getHighestAlbums()] == ["21", "12"]
