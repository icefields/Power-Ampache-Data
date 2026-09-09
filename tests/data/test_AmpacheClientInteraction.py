"""Interaction tier: flag()/rate() — mutating calls, write-through re-fetch,
read-back verification. FakeTransport + scratch DB from schema.sql."""
import sqlite3

import pytest

from ampachedata import (
    AccessDeniedError,
    CacheVerificationError,
    InvalidHandshakeError,
    ObjectType,
)


def _with(payload, **overrides):
    copy = dict(payload)
    copy.update(overrides)
    return copy


def _scalar(dbPath, sql, args):
    connection = sqlite3.connect(dbPath)
    try:
        return connection.execute(sql, args).fetchone()[0]
    finally:
        connection.close()


def testFlagSuccessRefetchesAndRefreshesCache(dbPath, makeClient, seedCredentials, seedSession,
                                              flagPayload, songPayload):
    seedCredentials()
    seedSession()
    songId = songPayload["id"]
    client, transport = makeClient([flagPayload, _with(songPayload, flag=True)])
    song = client.flag(ObjectType.SONG, songId, True)
    assert [r["params"]["action"] for r in transport.requests] == ["flag", "song"]
    flagRequest = transport.requests[0]["params"]
    assert flagRequest["filter"] == str(songId)
    assert flagRequest["type"] == "song"
    assert flagRequest["flag"] == "1"
    assert song.flag is True
    assert _scalar(dbPath, "SELECT flag FROM SongEntity WHERE mediaId = ?", (songId,)) == 1


def testFlagDispatchesToEveryTypeGetter(dbPath, makeClient, seedCredentials, seedSession,
                                        flagPayload, songPayload, albumPayload,
                                        artistPayload, playlistPayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([
        flagPayload, _with(songPayload, flag=True),
        flagPayload, _with(albumPayload, flag=True),
        flagPayload, _with(artistPayload, flag=True),
        flagPayload, _with(playlistPayload, flag=True),
    ])
    assert client.flag(ObjectType.SONG, songPayload["id"], True).flag is True
    assert client.flag(ObjectType.ALBUM, albumPayload["id"], True).flag is True
    assert client.flag(ObjectType.ARTIST, artistPayload["id"], True).flag is True
    assert client.flag(ObjectType.PLAYLIST, playlistPayload["id"], True).flag is True
    assert [r["params"]["action"] for r in transport.requests] == [
        "flag", "song", "flag", "album", "flag", "artist", "flag", "playlist",
    ]


@pytest.mark.parametrize("badRating", [6, -1])
def testRateOutOfRangeRaisesLocallyNoNetwork(makeClient, seedCredentials, seedSession, badRating):
    seedCredentials()
    seedSession()
    client, transport = makeClient([])  # empty queue: any send would fail the test
    with pytest.raises(ValueError):
        client.rate(ObjectType.SONG, "1", badRating)
    assert transport.requests == []


def testRateSuccessRefetchesAndRefreshesCache(dbPath, makeClient, seedCredentials, seedSession,
                                              ratePayload, songPayload):
    seedCredentials()
    seedSession()
    songId = songPayload["id"]
    client, transport = makeClient([ratePayload, _with(songPayload, rating=4)])
    song = client.rate(ObjectType.SONG, songId, 4)
    assert [r["params"]["action"] for r in transport.requests] == ["rate", "song"]
    rateRequest = transport.requests[0]["params"]
    assert rateRequest["filter"] == str(songId)
    assert rateRequest["type"] == "song"
    assert rateRequest["rating"] == "4"
    assert song.rating == 4
    assert _scalar(dbPath, "SELECT rating FROM SongEntity WHERE mediaId = ?", (songId,)) == 4


def testRateArtistSkipsVerificationNoRatingColumn(dbPath, makeClient, seedCredentials,
                                                  seedSession, ratePayload, artistPayload):
    """ArtistEntity has no rating column: server-side rate + re-fetch still
    happen, verification is skipped (documented limitation)."""
    seedCredentials()
    seedSession()
    client, transport = makeClient([ratePayload, artistPayload])
    artist = client.rate(ObjectType.ARTIST, artistPayload["id"], 5)
    assert [r["params"]["action"] for r in transport.requests] == ["rate", "artist"]
    assert artist.id == artistPayload["id"]


def testFlagMismatchRaisesCacheVerificationError(dbPath, makeClient, seedCredentials,
                                                 seedSession, flagPayload, songPayload):
    seedCredentials()
    seedSession()
    # Server confirms, but the re-fetched object still has flag unset.
    client, _ = makeClient([flagPayload, _with(songPayload, flag=False)])
    with pytest.raises(CacheVerificationError):
        client.flag(ObjectType.SONG, songPayload["id"], True)


def testRateMismatchRaisesCacheVerificationError(dbPath, makeClient, seedCredentials,
                                                 seedSession, ratePayload, songPayload):
    seedCredentials()
    seedSession()
    client, _ = makeClient([ratePayload, _with(songPayload, rating=0)])
    with pytest.raises(CacheVerificationError):
        client.rate(ObjectType.SONG, songPayload["id"], 4)


def testErrorEnvelopeRaisesNoRefetchNoDbWrite(dbPath, makeClient, seedCredentials, seedSession):
    seedCredentials()
    seedSession()
    errorPayload = {"error": {"code": "4703", "message": "Access denied"}}
    client, transport = makeClient([errorPayload])
    with pytest.raises(AccessDeniedError):
        client.flag(ObjectType.SONG, "1", True)
    assert len(transport.requests) == 1  # no re-fetch
    assert _scalar(dbPath, "SELECT COUNT(*) FROM SongEntity", ()) == 0  # no DB write


def testFlagAfterGoodbyeRaises(makeClient, seedCredentials, seedSession, goodbyePayload):
    seedCredentials()
    seedSession()
    client, transport = makeClient([goodbyePayload])
    client.goodbye()
    with pytest.raises(InvalidHandshakeError):
        client.flag(ObjectType.SONG, "1", True)
    assert [r["params"]["action"] for r in transport.requests] == ["goodbye"]
