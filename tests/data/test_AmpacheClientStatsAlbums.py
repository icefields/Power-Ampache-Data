# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""stats (type=album) write-through flows through the fake transport. No network.

filter is ALWAYS sent explicitly (the API default is random — never
inherited). limit semantics come from _fetchAllPages: no limit -> full
pages until total_count; explicit limit -> the caller's window, verbatim.

NO HistoryEntity rows are written for albums: mapHistory is song-shaped
and AlbumEntity has no play columns. The read-back therefore cannot be
DB-derived for ANY filter — every method (not just random) uses the
explicit CONVENTIONS 'persist, read back from response' allowance: the
ORDER comes from the response while entity data still comes only from
the DB (read back by id via getAlbum, in response order)."""
import sqlite3

import pytest

from ampachedata import AmpacheError

HANDSHAKE_AUTH = "0c45633f51b0e264a2260ebfa406e1ad"


def testGetRecentAlbumsWriteThroughAndReadBack(dbPath, makeClient, seedCredentials,
                                               seedSession, statsAlbumPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([statsAlbumPayload])
    albums = client.getRecentAlbums()
    # read-back order comes from the response: 21 before 12
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
    reversedPayload = dict(statsAlbumPayload)
    reversedPayload["album"] = list(reversed(statsAlbumPayload["album"]))
    client, _ = makeClient([reversedPayload])
    assert [a.id for a in client.getFrequentAlbums()] == ["12", "21"]  # response order


def testGetForgottenAlbumsSendsFilterAndReadsBack(makeClient, seedCredentials, seedSession,
                                                  statsAlbumPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([statsAlbumPayload])
    albums = client.getForgottenAlbums()
    assert [a.id for a in albums] == ["21", "12"]
    assert transport.requests[0]["params"]["filter"] == "forgotten"
    reversedPayload = dict(statsAlbumPayload)
    reversedPayload["album"] = list(reversed(statsAlbumPayload["album"]))
    client, _ = makeClient([reversedPayload])
    assert [a.id for a in client.getForgottenAlbums()] == ["12", "21"]  # response order


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
    # read-back order comes from the response: 21 before 12
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
    reversedPayload = dict(statsAlbumPayload)
    reversedPayload["album"] = list(reversed(statsAlbumPayload["album"]))
    client, _ = makeClient([reversedPayload])
    assert [a.id for a in client.getHighestAlbums()] == ["12", "21"]  # response order


def testNewestAndHighestAlbumsReadBackIsResponseOrder(makeClient, seedCredentials,
                                                      seedSession, statsAlbumPayload):
    """Response order wins for newest/highest too: the reversed response
    (12 before 21) is returned verbatim — the same read-back shape as
    random, not the old (year, searchName) cache order."""
    seedCredentials()
    seedSession()
    reversedPayload = dict(statsAlbumPayload)
    reversedPayload["album"] = list(reversed(statsAlbumPayload["album"]))
    client, _ = makeClient([reversedPayload, reversedPayload])
    assert [a.id for a in client.getNewestAlbums()] == ["12", "21"]
    assert [a.id for a in client.getHighestAlbums()] == ["12", "21"]


@pytest.mark.parametrize("methodName", [
    "getRecentAlbums",
    "getFrequentAlbums",
    "getForgottenAlbums",
    "getNewestAlbums",
    "getHighestAlbums",
])
def testStatsAlbumsMissingReadBackRowRaises(dbPath, makeClient, seedCredentials,
                                            seedSession, statsAlbumPayload,
                                            monkeypatch, methodName):
    """A response id that the write-through failed to persist raises the
    same AmpacheError getRandomAlbums raises — never a silent skip."""
    seedCredentials()
    seedSession()
    client, _ = makeClient([statsAlbumPayload])
    monkeypatch.setattr(client._albumRepository, "getAlbum", lambda albumId: None)
    with pytest.raises(AmpacheError, match="missing from DB after write-through"):
        getattr(client, methodName)()
